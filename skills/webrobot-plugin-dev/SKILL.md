---
name: webrobot-plugin-dev
description: Build WebroBot plugins — custom ETL stages (Scala SDK) and REST API endpoints (Java JAX-RS). Use when the user wants to create a new plugin, add a custom stage, extend the REST API, or understand the plugin architecture.
argument-hint: [plugin type and description, e.g. "ETL stage to save leads to CRM" or "REST API plugin for price comparison"]
user-invocable: true
allowed-tools: Read Write Edit Bash(gradle *) Bash(mvn *) Bash(JAVA_HOME=* ./gradlew *) Bash(JAVA_HOME=* mvn *)
---

# WebroBot Plugin Developer

WebroBot plugins extend the platform without modifying the core. Two complementary plugin types:

| Plugin type | Language | Mechanism | When to use |
|-------------|----------|-----------|-------------|
| **ETL plugin** | Scala / Gradle | Java ServiceLoader | Custom pipeline stages (transform, sink, source) |
| **REST API plugin** | Java / Maven | JAX-RS + manifest.json | New API endpoints, domain data management, job orchestration |

Reference implementation: **webrobot-price-comparison**
`https://github.com/WebRobot-Ltd/webrobot-price-comparison`

---

## ETL plugin (Scala)

### Module structure

```
my-plugin/
  build.gradle.kts
  src/main/
    scala/com/example/plugin/
      MyTransformStage.scala
      MySinkStage.scala
    resources/META-INF/services/
      eu.webrobot.plugin.sdk.WTransformStage
      eu.webrobot.plugin.sdk.WSinkStage
  manifest.json
```

### build.gradle.kts

```kotlin
plugins {
    id("scala")
    id("java-library")
}
group = "com.example"
version = "1.0.0"

dependencies {
    compileOnly(project(":webrobot-plugin-sdk"))           // provided at runtime by engine
    compileOnly("org.scala-lang:scala-library:2.13.12")
    compileOnly("org.slf4j:slf4j-api:1.7.36")
}
```

### Stage types

#### WTransformStage — row in, row out (no DB access)

```scala
import eu.webrobot.plugin.sdk.{WArgs, WRow, WTransformStage}

class MyTransformStage extends WTransformStage {

  override val name: String = "my_stage_id"   // ID used in pipeline YAML

  override def transform(row: WRow, args: WArgs): WRow = {
    val inputField  = args.string(0, "input_col")   // positional arg, with default
    val threshold   = args.double(1, 0.5)

    val value = row.str(inputField).getOrElse("")
    val score = computeScore(value)

    row.set("my_score", score)       // set returns a new WRow (immutable)
        .set("my_label", if (score >= threshold) "high" else "low")
  }

  private def computeScore(s: String): Double = ???
}
```

#### WSinkStage — row in, side effect (DB write), row out

```scala
import eu.webrobot.plugin.sdk.{WArgs, WRow, WSinkStage, WebroStageContext}

class MySinkStage extends WSinkStage {

  override val name: String = "my_sink_id"

  private val insertSql =
    "INSERT INTO my_table (org_id, value, created_at) VALUES (?, ?, NOW())"

  override def consume(row: WRow, args: WArgs, ctx: WebroStageContext): WRow = {
    val orgId = resolveOrgId(row, ctx)
    val value = row.str("my_field").getOrElse(
      throw new IllegalStateException("my_field is required"))

    val affected = ctx.execute(insertSql, Seq[Any](orgId, value))
    if (affected != 1)
      ctx.warn(s"Expected 1 row inserted, got $affected")

    row   // pass through unchanged
  }

  private def resolveOrgId(row: WRow, ctx: WebroStageContext): Long =
    row.get("org_id").orElse(row.get("organization_id"))
      .map(_.toString.toLong)
      .orElse {
        val v = ctx.config("webrobot.org.id")
        if (v.nonEmpty) Some(v.toLong) else None
      }
      .getOrElse(throw new IllegalStateException("organization_id not found"))
}
```

### WRow API

| Method | Returns | Notes |
|--------|---------|-------|
| `row.str("field")` | `Option[String]` | Prefer over `get()` for strings |
| `row.double("field")` | `Option[Double]` | Returns None if missing or not numeric |
| `row.get("field")` | `Option[Any]` | Raw value |
| `row.set("field", value)` | `WRow` | Returns new row — immutable |

`Option[Double].orNull` does NOT compile — box first: `.map(java.lang.Double.valueOf).orNull`

### WArgs API

```scala
args.string(0, "default")   // positional index, default value
args.double(1, 0.90)
args.int(2, 10)
```

### WebroStageContext API

```scala
// DB read — returns Iterator[WRow]
val rows = ctx.query("SELECT id FROM table WHERE org_id = ?", Seq[Any](orgId))
while (rows.hasNext) { val row = rows.next(); ... }

// DB write — returns Int (rows affected)
val n = ctx.execute("INSERT INTO ...", Seq[Any](...))

// IMPORTANT: never use ctx.query() for INSERT/UPDATE — use ctx.execute()
// Separate execute() + query() for UPSERT+RETURNING patterns

// HTTP call
val resp = ctx.httpPost("https://api.example.com/v1/infer", jsonBody, Map("Authorization" -> s"Bearer $key"))

// Config / env
val apiKey = ctx.config("GROQ_API_KEY")   // from cloud credentials env injection

// Logging
ctx.warn("something unexpected happened")
```

### ServiceLoader registration

`src/main/resources/META-INF/services/eu.webrobot.plugin.sdk.WTransformStage`:
```
com.example.plugin.MyTransformStage
com.example.plugin.AnotherTransformStage
```

`src/main/resources/META-INF/services/eu.webrobot.plugin.sdk.WSinkStage`:
```
com.example.plugin.MySinkStage
```

One class name per line. File name must match the fully-qualified interface name exactly.

### manifest.json

```json
{
  "name": "my-plugin",
  "version": "1.0.0",
  "description": "Short description for the platform UI",
  "stages": [
    {
      "id": "my_stage_id",
      "type": "transform",
      "description": "What this stage does",
      "args": [
        { "name": "input_col", "type": "string", "default": "input", "description": "Source field" },
        { "name": "threshold", "type": "double", "default": "0.5",   "description": "Score threshold" }
      ]
    },
    {
      "id": "my_sink_id",
      "type": "sink",
      "description": "Saves to DB",
      "args": []
    }
  ]
}
```

### Build

```bash
JAVA_HOME=/home/roger/.jdks/openjdk-21 ./gradlew :my-plugin:jar
```

### Non-Serializable fields (HttpClient etc.)

Mark as `@transient lazy val` to survive Spark serialization:

```scala
// @transient: re-created after deserialization on each executor
@transient private lazy val http: java.net.http.HttpClient =
  java.net.http.HttpClient.newBuilder()
    .connectTimeout(java.time.Duration.ofSeconds(10))
    .build()
```

---

## REST API plugin (Java)

### Module structure

```
my-rest-plugin/
  pom.xml
  manifest.json
  src/main/java/org/example/plugin/
    MyPlugin.java         # JAX-RS resource (endpoint registration)
    MyService.java        # Business logic + DB access
  src/main/resources/db/migration/my_domain/
    V1__init.sql
    V2__add_table.sql
```

### pom.xml (key dependencies)

```xml
<parent>
    <groupId>webrobot.eu</groupId>
    <artifactId>webrobot-etl-api-parent</artifactId>
    <relativePath>../pom.xml</relativePath>
</parent>

<dependencies>
    <!-- provided at runtime by the platform -->
    <dependency><groupId>webrobot.eu</groupId><artifactId>org.webrobot.eu.kernel.common</artifactId><scope>provided</scope></dependency>
    <dependency><groupId>webrobot.eu</groupId><artifactId>org.webrobot.eu.apis.jersey</artifactId><scope>provided</scope></dependency>
</dependencies>
```

### JAX-RS resource class

```java
@Singleton                          // REQUIRED — one instance per deployment
@Path("/webrobot/api/my-domain")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
public class MyPlugin {

    private final MyService service = new MyService();

    @GET
    @Path("/items")
    @RequiresScopes("read")
    public Response listItems(@Context ContainerRequestContext req) {
        try {
            String orgId = OrganizationContextHelper.getOrganizationId(req);
            return Response.ok(service.listItems(orgId)).build();
        } catch (Exception e) {
            return Response.serverError().entity(Map.of("error", e.getMessage())).build();
        }
    }

    @POST
    @Path("/items")
    @RequiresScopes("write")
    public Response addItem(@Context ContainerRequestContext req, Map<String, Object> body) {
        try {
            String orgId = OrganizationContextHelper.getOrganizationId(req);
            String name  = require(body, "name");   // validate required field
            return Response.ok(service.addItem(orgId, name)).build();
        } catch (IllegalArgumentException e) {
            return Response.status(400).entity(Map.of("error", e.getMessage())).build();
        } catch (Exception e) {
            return Response.serverError().entity(Map.of("error", e.getMessage())).build();
        }
    }

    private String require(Map<String, Object> body, String key) {
        Object v = body == null ? null : body.get(key);
        if (v == null || v.toString().isBlank())
            throw new IllegalArgumentException("Required field missing: " + key);
        return v.toString().trim();
    }
}
```

### Multi-tenancy (mandatory)

- `organization_id` on every domain table
- Resolved from JWT: `OrganizationContextHelper.getOrganizationId(req)` — **never** from request body
- All queries must filter by `organization_id`

### JDBC access pattern

```java
private Connection getConnection() throws SQLException {
    Properties props = new Properties();
    props.setProperty("user",         System.getenv("DB_USER"));
    props.setProperty("password",     System.getenv("DB_PASSWORD"));
    props.setProperty("loginTimeout", "5");
    return DriverManager.getConnection(System.getenv("DB_JDBC_URL"), props);
}

// Always try-with-resources for both Connection and PreparedStatement
public List<Map<String, Object>> listItems(String orgId) throws Exception {
    try (Connection conn = getConnection();
         PreparedStatement ps = conn.prepareStatement(
            "SELECT id, name FROM my_items WHERE organization_id = ? ORDER BY name")) {
        ps.setLong(1, Long.parseLong(orgId));
        return resultSetToList(ps.executeQuery());
    }
}
```

### Kernel ORM services (for project/agent/job management)

```java
// Correct method names — verified against kernel source
MyBatisProjectService  projectService  = new MyBatisProjectService();
MyBatisAgentService    agentService    = new MyBatisAgentService();
MyBatisDatasetService  datasetService  = new MyBatisDatasetService();
MyBatisJobService      jobService      = new MyBatisJobService();

// Project — create and lookup
Project p = new Project();
p.setName("my-project-org-" + orgId);
p.setOrganizationId(orgId);          // String, not long
p.setDescription("...");
p = projectService.create(p);        // NOT .save()
Project found = projectService.findByName(name);  // returns null if not found

// Agent — no setProjectId; linked to project via Job
Agent a = new Agent();
a.setName("my-agent-org-" + orgId);
a.setOrganizationId(orgId);          // String
a.setPipelineYaml(yaml);
a = agentService.create(a);

// Dataset
Dataset d = new Dataset();
d.setName("...");
d.setStoragePath(csvPath);           // NOT setFilePath
d.setOrganizationId(orgId);          // String
d.setCreatedAt(new java.util.Date()); // explicit java.util.Date (avoid sql.* import ambiguity)
d = datasetService.create(d);

// Job — use object refs, not ID setters
Job job = new Job();
job.setProject(project);             // NOT setProjectId
job.setAgent(agent);                 // NOT setAgentId
job.setInputDataset(dataset);        // NOT setDatasetId
job.setOrganizationId(orgId);        // String
job.setExecutionStatus(ExecutionStatus.PENDING);
// import org.webrobot.eu.kernel.common.domain.orm.ExecutionStatus;
job = jobService.create(job);
```

### Flyway migrations

Place SQL files in `src/main/resources/db/migration/<domain>/`:

```sql
-- V1__init_my_domain.sql
CREATE TABLE IF NOT EXISTS my_items (
    id              BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL,
    name            VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (organization_id, name)
);
CREATE INDEX IF NOT EXISTS idx_my_items_org ON my_items (organization_id);
```

### manifest.json (REST API plugin)

```json
{
  "name": "my-rest-plugin",
  "version": "1.0.0",
  "type": "rest-api",
  "description": "Domain-specific REST endpoints",
  "entrypoint": "org.example.plugin.MyPlugin"
}
```

### Build

```bash
JAVA_HOME=/home/roger/.jdks/openjdk-21 \
  /home/roger/Projects/tools-and-infra/tools/idea-IU-232.9921.47/plugins/maven/lib/maven3/bin/mvn \
  compile
```

---

## Price comparison plugin — reference

ETL plugin (Scala): `webrobot-etl/webrobot-plugin-price-comparison/`
REST API plugin (Java): `rest-api/WebRobotAPIS-new/org.webrobot.eu.apis.jersey.price-comparison.plugin/`

### Four ETL stages

| Stage ID | Type | Description |
|----------|------|-------------|
| `pc_match_scorer` | WTransformStage | EAN exact match (0.95) → Jaccard title sim (0.50–0.85) |
| `pc_image_match_stage` | WTransformStage | Groq vision LLM comparison; skipped if confidence ≥ 0.90 |
| `pc_save_match` | WSinkStage | UPSERT into pc_matches; sets match_id on row |
| `pc_save_price` | WSinkStage | INSERT into pc_price_history; requires match_id > 0 |

### Discovery pipeline (phase 1)
```yaml
load_csv → searchEngine → visit → iextract → pc_match_scorer → pc_image_match_stage → pc_save_match
```

### Monitoring pipeline (phase 2)
```yaml
load_csv → visit → iextract → pc_save_price
```

### REST endpoints

| Method | Path | Scope |
|--------|------|-------|
| POST | `/webrobot/api/price-comparison/bootstrap` | admin |
| GET/POST/DELETE | `/webrobot/api/price-comparison/products` | read/write |
| GET/POST/DELETE | `/webrobot/api/price-comparison/competitors` | read/write |
| POST | `/webrobot/api/price-comparison/jobs/discovery` | write |
| POST | `/webrobot/api/price-comparison/jobs/monitoring` | write |
| GET | `/webrobot/api/price-comparison/prices` | read |
| GET | `/webrobot/api/price-comparison/matches` | read |

---

## Common pitfalls

- `@Singleton` missing on JAX-RS resource → new service instance per request
- `ctx.query()` used for DML → use `ctx.execute()` for writes, `ctx.query()` only for SELECT
- `Option[Double].orNull` → box first: `.map(java.lang.Double.valueOf).orNull`
- `new Date()` ambiguous when `import java.sql.*` is in scope → use `new java.util.Date()`
- `setProjectId/AgentId/DatasetId` on Job don't exist → use `setProject/Agent/InputDataset` (object refs)
- `setOrganizationId` takes `String` everywhere in kernel ORM, not `long`
- `projectService.save()` doesn't exist → use `.create()` and `.update()`
- `@transient lazy val` required for non-Serializable fields (HttpClient, etc.) in Spark stages
