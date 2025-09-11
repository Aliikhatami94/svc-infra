# MongoDB Commands

## 📦 Mongo Scaffold Commands

### 1. `mongo-scaffold`
Generate both document + CRUD schemas.

```bash
svc-infra mongo-scaffold \
  --entity-name Product \
  --documents-dir app/db/mongo/documents \
  --schemas-dir app/db/mongo/documents  \
  --same-dir
```

### 2. `mongo-scaffold-documents`
Generate only the Mongo document model (Pydantic).

```bash
svc-infra mongo-scaffold-documents \
  --dest-dir app/db/mongo/documents \
  --entity-name Product
```

### 3. `mongo-scaffold-schemas`
Generate only the CRUD schemas (Pydantic).

```bash
svc-infra mongo-scaffold-schemas \
  --dest-dir app/db/mongo/schemas \
  --entity-name Product
```

### 4. `mongo-scaffold-resources`
Generate a starter resources.py file with an empty RESOURCES list and index_builders().

```bash
svc-infra mongo-scaffold-resources \
  --dest-dir app/db/mongo \
  --entity-name Product
```

---

## 🗄 Mongo Database Commands

### 5. `mongo-prepare`
Ensure Mongo is reachable, create collections, and apply indexes.

```bash
svc-infra mongo-prepare \
  --resources app.db.mongo.resources:RESOURCES \
  --index-builders app.db.mongo.resources:index_builders
```

### 6. `mongo-setup-and-prepare`
End-to-end: resolve env, init client, ensure collections & indexes, close client.

```bash
svc-infra mongo-setup-and-prepare \
  --resources src.apiframeworks_api.mongo.resources:RESOURCES \
  --index-builders src.apiframeworks_api.mongo.resources:index_builders
```

### 7. `mongo-ping`
Connectivity check (db.command("ping")).

```bash
svc-infra mongo-ping
```

---

## ✅ Summary

In total you have **7 CLI commands**:

- `mongo-scaffold`
- `mongo-scaffold-documents`
- `mongo-scaffold-schemas`
- `mongo-scaffold-resources`
- `mongo-prepare`
- `mongo-setup-and-prepare`
- `mongo-ping`

---
