---
name: webrobot-sdk-java
description: Consume the WebRobot REST API from a Java/Kotlin/Scala application using the public webrobot-sdk JAR. Use when the user wants to integrate WebRobot into a JVM service, build automation, or partner application — NOT for writing ETL/Jersey plugins (those use a different SDK; see /webrobot-plugin-dev).
argument-hint: [task description, e.g. "list projects from my Spring Boot app"]
user-invocable: true
allowed-tools: Read Write Edit Bash(mvn *) Bash(JAVA_HOME=* mvn *) Bash(./gradlew *) Bash(JAVA_HOME=* ./gradlew *) Bash(curl -fsSL https://api.webrobot.eu/webrobot/api/catalog/stages*)
---

# WebRobot Java SDK (client)

You help the user consume the WebRobot REST API as a CLIENT from a JVM application. The SDK is auto-generated from the OpenAPI spec (138 endpoints) plus a hand-written facade (`OpenApiSdkAdapter` + `GenericClient`) that hides the OpenAPI generator's verbose call shape.

**Not for plugin development.** If the user is building an ETL stage or REST API plugin that runs INSIDE the platform, use `/webrobot-plugin-dev`. That uses a different SDK (`webrobot-plugin-sdk` / `webrobot-jersey-plugin-sdk`).

---

## Install (Maven via JitPack — no auth required)

```xml
<repositories>
  <repository>
    <id>jitpack.io</id>
    <url>https://jitpack.io</url>
  </repository>
</repositories>

<dependencies>
  <dependency>
    <groupId>com.github.WebRobot-Ltd</groupId>
    <artifactId>webrobot-sdk</artifactId>
    <version>v0.3.14</version>
  </dependency>
</dependencies>
```

Gradle (Kotlin DSL):
```kotlin
repositories {
    mavenCentral()
    maven { url = uri("https://jitpack.io") }
}
dependencies {
    implementation("com.github.WebRobot-Ltd:webrobot-sdk:v0.3.14")
}
```

JDK 17+ required.

---

## Auth

Two modes. Pick one — never both.

```java
import WebRobot.Cli.Sdk.openapi.OpenApiSdkAdapter;
import eu.webrobot.openapi.client.ApiClient;
import eu.webrobot.openapi.client.api.DefaultApi;

OpenApiSdkAdapter sdk = new OpenApiSdkAdapter("https://api.webrobot.eu");

// Option A — API key (recommended for service-to-service)
sdk.withApiKey("X-API-Key", System.getenv("WEBROBOT_API_KEY"));

// Option B — JWT bearer (recommended when user-context is needed)
sdk.withApiKey("Authorization", "Bearer " + System.getenv("WEBROBOT_JWT"));

ApiClient   apiClient = sdk.getApiClient();
DefaultApi  api       = sdk.api();
```

For local development, the same `~/.webrobot/config.cfg` used by the WebRobot CLI works — no need to duplicate keys. The Java SDK doesn't auto-load it; either parse the HOCON yourself or use env vars.

---

## Two ways to call

### 1. Typed `DefaultApi` — auto-generated, all 138 endpoints

```java
DefaultApi api = sdk.api();

// List all projects in the caller's org
List<Object> projects = api.getAllProjects(/* x_rapid_api_user */ null);

// Get one project
Object project = api.getProjectById("42", null);

// Create a project
JobProjectDto project = new JobProjectDto();
project.setName("price-comparison");
project.setDescription("...");
api.createProject(project, null);

// Execute a job
api.executeJob("42", "7", null);
```

Method names follow camelCase variants of the path (`/webrobot/api/projects` → `getAllProjects`, `/webrobot/api/projects/id/{id}/jobs/{jobId}/execute` → `executeJob`). Browse the full surface in the JAR (`javap eu.webrobot.openapi.client.api.DefaultApi`) or rely on IDE autocomplete.

### 2. Generic `GenericClient` — endpoint-agnostic, hides JAX-RS/Pair/TypeReference

```java
import WebRobot.Cli.Sdk.openapi.GenericClient;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.Map;

GenericClient gc = sdk.generic();

// GET with path templating — {placeholders} substituted from queryParams,
// matching keys removed from the query string
JsonNode resp = gc.get("/webrobot/api/projects/{id}/jobs",
                       Map.of("id", "42", "limit", "100"));

// POST
JsonNode created = gc.post("/webrobot/api/projects",
                           Map.of("name", "demo", "description", "..."));

// PUT/PATCH/DELETE analogous

// Streaming SSE
try (Stream<JsonNode> events =
        gc.stream("/webrobot/api/jobs/{id}/logs", Map.of("id", "42"))) {
    events.forEach(line -> System.out.println(line.get("message").asText()));
}

// Typed sugar — Jackson maps response body to a DTO
MyDto dto = gc.get("/webrobot/api/my-resource/{id}",
                   Map.of("id", "1"),
                   MyDto.class);
List<MyDto> list = gc.getList("/webrobot/api/my-resources",
                              Map.of(),
                              MyDto.class);
```

Use `GenericClient` when: a partner-vertical endpoint isn't yet in `DefaultApi` (e.g. `/webrobot/api/sentiment/timeseries`), the response is dynamic JSON, or you want to skip the verbose typed DTOs.

---

## Public catalog endpoint — no auth required

```java
// Discover available pipeline stages (zero auth — public read-only endpoint)
JsonNode stages = gc.get("/webrobot/api/catalog/stages",
                         Map.of("plugin_type", "etl"));
```

Useful for building a UI that lets users pick stages, or for AI-driven pipeline construction.

---

## Error handling

```java
import WebRobot.Cli.Sdk.openapi.GenericApiException;

try {
    gc.get("/webrobot/api/projects/9999", Map.of());
} catch (GenericApiException e) {
    e.statusCode();   // 404
    e.errorBody();    // raw JSON
    e.headers();      // List<String> per header (multi-valued)
    e.requestId();    // X-Request-Id when present
}
```

The typed `DefaultApi` throws `eu.webrobot.openapi.client.ApiException` instead — same fields but different class.

---

## When to use the Java SDK vs alternatives

| Need | Tool |
|------|------|
| JVM service / Spring Boot / Micronaut backend | **Java SDK** (this) |
| Shell script / CI pipeline | `webrobot` CLI |
| Conversational queries from Claude Code / Cursor | MCP tools (`mcp__webrobot__*`) |
| Inside the ETL engine (custom stage) | `webrobot-plugin-sdk` (Scala SDK) — see `/webrobot-plugin-dev` |
| Inside a Jersey API plugin | `webrobot-jersey-plugin-sdk` — see `/webrobot-plugin-dev` |

---

## Common patterns

### Wait for a job to complete

```java
String projectId = "42", jobId = "7";
api.executeJob(projectId, jobId, null);
while (true) {
    JsonNode status = gc.get("/webrobot/api/projects/{p}/jobs/{j}",
                             Map.of("p", projectId, "j", jobId));
    String s = status.path("status").asText();
    if ("COMPLETED".equals(s) || "FAILED".equals(s) || "CANCELLED".equals(s)) {
        System.out.println("Final status: " + s);
        break;
    }
    Thread.sleep(10_000);
}
```

### Stream job logs

```java
try (Stream<JsonNode> logs =
        gc.stream("/webrobot/api/projects/{p}/jobs/{j}/logs",
                  Map.of("p", "42", "j", "7", "tail", "200"))) {
    logs.forEach(entry -> System.out.println(
        entry.path("timestamp").asText() + " [" + entry.path("level").asText() + "] " +
        entry.path("message").asText()));
}
```

### Run a pipeline manifest from code

```java
String yaml = Files.readString(Paths.get("pipeline.yaml"));
JsonNode result = gc.post("/webrobot/api/pipelines/run", Map.of(
    "yaml", yaml,
    "follow", true
));
String executionId = result.path("executionId").asText();
```

---

## Rules of thumb

- **Use the typed `DefaultApi`** for endpoints documented in OpenAPI — type safety + IDE autocomplete.
- **Use `GenericClient`** for partner-vertical endpoints, dynamic responses, or path-templated GETs you find boilerplate.
- **Never embed credentials in source.** Use env vars (`WEBROBOT_API_KEY` / `WEBROBOT_JWT`) or a config file outside the repo.
- **Catch `GenericApiException` / `ApiException`** explicitly — both expose statusCode/errorBody for structured handling.
- **The catalog endpoint is public.** Don't put auth headers on `/webrobot/api/catalog/stages` — they're ignored anyway, and your client handles the response uniformly.

## On $ARGUMENTS

- If the user passed a task description: scaffold the Java code that does it, show the imports, run it if a build environment is available.
- If the user passed a file path: read it, propose the SDK call to add.
- If the user is unclear: ask whether they want typed `DefaultApi` calls or generic `GenericClient` for an arbitrary endpoint.
