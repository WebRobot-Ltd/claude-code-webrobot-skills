---
name: webrobot-datasets
description: Work with WebRobot datasets. List and inspect them, upload a CSV (REST multipart or the MCP uploadDatasetJson tool), read columns, run read-only SQL with executeQuery (the [datasetId] shortcut) or queryDatasetByTask (the {table} placeholder), find the output dataset of a job run, and export rows. Use when the user wants to upload data, look at a dataset, query or export results, or find what a job produced.
argument-hint: [dataset task, e.g. "upload sales.csv and sum by region" or "show the output of job 812"]
user-invocable: true
---

# WebRobot datasets

Setup, API key and the REST prefix are covered in the `webrobot-setup` skill. In the examples below:

```bash
export WR=https://api.webrobot.eu/api/webrobot/api
H="X-API-Key: $WEBROBOT_API_KEY"
```

Everything is scoped to the key's organization. Other orgs' datasets answer 404, or 403 for SQL. A viewer key is read-only, and developer/viewer keys see only the datasets of projects they are assigned to.

## Model

- **INPUT** datasets are files you upload. **OUTPUT** datasets are written by job runs.
- Files live in object storage under `org/<orgId>/...`. SQL runs on Trino, where each dataset is an internal table, catalog `minio`, schema `default`.
- Every task of a job run points at its output dataset (`task.outputDatasetId`). If a run creates one, its name is `Job Output - <job name> - <yyyy-MM-dd HH:mm:ss>`.

## List and inspect

| Task | MCP tool | REST |
|---|---|---|
| List (filters: `type`=INPUT/OUTPUT, `format`=CSV/JSON/PARQUET, `indexed`=true/false) | `getAllDatasets` | `GET $WR/datasets?type=OUTPUT` |
| One dataset | `getDataset` (`datasetId`) | `GET $WR/datasets/{id}` |
| Columns | `getDatasetFields` (`datasetId`) | `GET $WR/datasets/{id}/fields` |
| Rename / describe | `updateDataset` (`datasetId`, `name`, `description`) | `PUT $WR/datasets/{id}` |
| Delete | `deleteDataset` | `DELETE $WR/datasets/{id}` |

`getDatasetFields` returns `[{id,name,type,nullable,description}]`. For a CSV that hasn't been catalogued yet, it reads the column names from the file header (type guessed from row 2). **Use these exact names in SQL**: don't guess them.

## Upload a CSV

**Option A: one JSON call (works over MCP).** Use the `uploadDatasetJson` tool:

```
uploadDatasetJson(name="sales_2024", filename="sales.csv", dataset_type="input",
                  content="region,month,revenue_eur\nNorth,2024-01,1200\nSouth,2024-01,980\n")
→ {datasetId, name, organizationId, storagePath, filePath}
```

For large or non-UTF-8 files, pass `content_base64` instead of `content`. The same over REST:

```bash
curl -s -X POST "$WR/datasets/upload-json" -H "$H" -H 'Content-Type: application/json' \
  -d "$(jq -n --arg c "$(cat sales.csv)" '{name:"sales_2024",filename:"sales.csv",datasetType:"input",content:$c}')"
```

**Option B: REST multipart, in two steps.** The multipart endpoint only stores the file. Then you register it:

```bash
# 1. store the file  -> {"storagePath":"s3a://.../org/<org>/datasets/input/<ts>-sales_2024/","filename":"sales.csv"}
SP=$(curl -s -X POST "$WR/datasets/upload" -H "$H" \
       -F file=@sales.csv -F datasetType=input -F name=sales_2024 | jq -r .storagePath)

# 2. register it as a dataset (an INPUT dataset is indexed in Trino on creation)
curl -s -X POST "$WR/datasets" -H "$H" -H 'Content-Type: application/json' \
  -d "{\"name\":\"sales_2024\",\"storagePath\":\"$SP\",\"format\":\"CSV\",\"datasetType\":\"INPUT\",\"enabled\":true}"
# -> {"id":"1234", ...}
```

Do not call `uploadDatasetFile` over MCP: MCP can't send multipart (HTTP 415). Use `uploadDatasetJson`, or curl as above.

If SQL on a freshly uploaded dataset says the table does not exist, ask an admin to run `indexDataset` (`POST $WR/datasets/{id}/index`, admin role) once.

## SQL

Both endpoints accept **one read-only `SELECT` or `WITH` statement**. Rejected:

- `;`, `--` or `/* */` comments
- double-quoted or back-quoted identifiers (`"Col Name"` → 403)
- comma joins (`FROM a, b`): use `JOIN`
- `information_schema` / system schemas
- tables of other orgs

Write column names unquoted, exactly as `getDatasetFields` returns them.

Response: `{success, columns:[...], data:[{col:val,...}], rowCount, executionTimeMs, error}`.

**Limits.** The `limit` parameter defaults to 1000 rows and is appended as `LIMIT n` only when your SQL contains no `limit`. To page, write it in the SQL with a stable order: `... ORDER BY id OFFSET 2000 LIMIT 1000`. Don't use the `offset` parameter, which is appended after the LIMIT.

### `executeQuery`: any of your datasets, by id

> Known issue (2026-11-18): on datasets produced by a job (parquet output) it can fail with `Catalog 'null'`. For those use `getTaskByOutputDataset` → `queryDatasetByTask` (below).

`POST $WR/datasets/query`, body `{"sql": "...", "limit": 1000}`. Write `[<datasetId>]` where the table goes. The server swaps it for the dataset's real table after checking that it belongs to your org. Several datasets can be joined:

```sql
SELECT region, SUM(revenue_eur) AS revenue FROM [1234] GROUP BY region ORDER BY revenue DESC
SELECT o.sku, o.price, c.price AS competitor FROM [1234] o JOIN [1250] c ON o.sku = c.sku
```

Don't pass `catalog` or `schema`: they are ignored for tenant keys. `getTableColumns` / `listTables` exist but need real table names. Prefer `[id]` together with `getDatasetFields`.

### `queryDatasetByTask`: the output of one run

`POST $WR/datasets/query/task/{taskId}`, body `{"sql": "SELECT ... FROM {table} ...", "limit": 100}`. `{table}` (or `${table}`) becomes the task's output table. Only that table may be read, and CTEs over it are allowed. With an empty `sql`, the server builds a `SELECT` of all columns. If the output isn't indexed yet, it indexes it first; a 412 `NOT_INDEXED` means that failed.

Response: `{taskId, datasetId, datasetName, tableName, query:{success,columns,data,rowCount,...}}`.

`getDatasetInfoByTask` (`GET $WR/datasets/query/task/{taskId}/info`) gives the output dataset id, name, storage path, `indexed`, `fullTableName` and `columns`. The reverse lookup is `getTaskByOutputDataset` (`GET $WR/datasets/query/by-dataset/{datasetId}/task`).

## Find the output dataset of a job run

1. You have `projectId`, `jobId` and the `executionId` from `executeJob_1`.
2. Call `waitForExecution` (`projectId`, `jobId`, `executionId`). Each call waits **at most 45 s** and returns `{executionId, status, statusString, terminal}`, so repeat until `terminal` is true. When the run succeeded, the response also carries **`taskId` and `outputDatasetId` of this run**. When it failed, it carries `logTail`.
3. Then query it with `queryDatasetByTask(taskId, sql="... FROM {table} ...")`. **Use this for job outputs**: on 2026-11-18 `executeQuery` with `[outputDatasetId]` failed on a Spark job's parquet output with `Catalog 'null'` (even after `indexDataset`), while `queryDatasetByTask` returned the rows. If you only have the dataset id, get the task with `getTaskByOutputDataset(datasetId)`.

Fallback: `getAllTasks` (`projectId`, `jobId`) or `list_13` (`jobId`) lists the tasks. The run's task is the one whose `executionReferenceId` equals the `executionId`. Don't just take "the latest task": it may belong to another run.

No task at hand? List the outputs and pick by name and date: `getAllDatasets(type="OUTPUT")`, then filter names starting with `Job Output - <job name> - `.

## Export

There is no file-download endpoint for datasets. Export by paging SQL into a file:

```bash
DS=1234; PAGE=5000; OFF=0; OUT=export.csv; : > $OUT
while :; do
  R=$(curl -s -X POST "$WR/datasets/query" -H "$H" -H 'Content-Type: application/json' \
      -d "{\"sql\":\"SELECT * FROM [$DS] ORDER BY 1 OFFSET $OFF LIMIT $PAGE\",\"limit\":$PAGE}")
  [ "$(echo "$R" | jq -r .success)" = true ] || { echo "$R"; break; }
  [ $OFF -eq 0 ] && echo "$R" | jq -r '.columns | @csv' >> $OUT
  echo "$R" | jq -r '.columns as $c | .data[] | [ $c[] as $k | .[$k] ] | @csv' >> $OUT
  [ "$(echo "$R" | jq -r .rowCount)" -lt $PAGE ] && break
  OFF=$((OFF+PAGE))
done
wc -l $OUT
```

Other ways out:

- `indexDatasetToElasticsearch` pushes a dataset into your Elasticsearch.
- `publishDataset` publishes a file to Hugging Face.
- `start_export_project` / `start_export_organization_with_options` (`includeDatasets`) export a whole project or org package, including dataset records.

## Worked examples

### 1. Upload a CSV and aggregate it (MCP only)

1. `getCurrentUser` to confirm the org.
2. `uploadDatasetJson(name="sales_2024", content="region,month,revenue_eur\nNorth,2024-01,1200\nNorth,2024-02,1350\nSouth,2024-01,980\n")` → `datasetId: 1234`.
3. `getDatasetFields(datasetId="1234")` → `region, month, revenue_eur`.
4. `executeQuery(sql="SELECT region, SUM(revenue_eur) AS revenue, COUNT(*) AS months FROM [1234] GROUP BY region ORDER BY revenue DESC", limit=100)`.

### 2. Run a job and read what it produced (REST)

```bash
P=520; J=812
EID=$(curl -s -X POST "$WR/projects/id/$P/jobs/$J/execute" -H "$H" \
        -H 'Content-Type: application/json' -d '{}' | jq -r .executionId)
# each wait call returns after <=45 s; loop until terminal
while :; do
  W=$(curl -s "$WR/projects/id/$P/jobs/$J/executions/$EID/wait?timeoutSec=45&logTail=50" -H "$H")
  [ "$(echo "$W" | jq -r .terminal)" = true ] && break
done
echo "$W" | jq '{statusString, taskId, outputDatasetId, logTail}'
TASK=$(echo "$W" | jq -r .taskId)
curl -s "$WR/datasets/query/task/$TASK/info" -H "$H" | jq '{datasetId,datasetName,indexed,columns}'
curl -s -X POST "$WR/datasets/query/task/$TASK" -H "$H" -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT * FROM {table} LIMIT 20"}' | jq '.query.data'
```

The same over MCP: `executeJob_1` → `waitForExecution`, repeated until `terminal` (it gives `taskId` and `outputDatasetId`) → `getDatasetInfoByTask` → `queryDatasetByTask(taskId=..., sql="SELECT * FROM {table} LIMIT 20")`.

### 3. Compare a run's output with an uploaded reference list

The scraped prices are in task 9876 (output dataset 1301). The reference catalog is uploaded dataset 1234 with columns `sku, list_price`.

```
executeQuery(sql="SELECT r.sku, r.list_price, o.price, o.price - r.list_price AS delta
                  FROM [1234] r JOIN [1301] o ON r.sku = o.sku
                  WHERE o.price < r.list_price ORDER BY delta LIMIT 200")
```

A task-scoped query can't join another table. Use `executeQuery` with `[id]` shortcuts for joins across datasets.

## Errors

| Error | Meaning |
|---|---|
| 403 `only one plain SELECT statement…` | `;`, a comment, or a quoted identifier is in the SQL. |
| 403 `comma joins are not allowed` | Rewrite `FROM a, b` as `JOIN`. |
| 403 `only {table} may be read here` | `queryDatasetByTask` read another table. Use `executeQuery`. |
| 403 `Access denied to dataset [id]` / 404 | The dataset belongs to another org, or to a project you're not assigned to. |
| 404 `Task … has no output dataset` | The run hasn't finished, or failed before writing. Check `getExecutionStatus_1` / `getExecutionLogs_1`. |
| 412 `NOT_INDEXED` | The output table could not be registered. Check that the run completed and wrote files. |
| 500 with Trino error text | SQL error, usually a wrong column name. Re-check with `getDatasetFields`. |
