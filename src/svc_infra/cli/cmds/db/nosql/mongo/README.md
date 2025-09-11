# MongoDB Commands

## 📦 Mongo Scaffold Commands

### 1. `mongo-scaffold`
Generate both document + CRUD schemas.

```bash
svc-infra mongo-scaffold \
  --entity-name Product \
  --documents-dir src/apiframeworks_api/mongo/products \
  --schemas-dir src/apiframeworks_api/mongo/products \
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
  --resources app.db.mongo.resources:RESOURCES \
  --index-builders app.db.mongo.resources:index_builders
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

## 💡 Future Enhancement

Do you want me to also mirror the SQL setup-and-migrate style convenience command (single end-to-end entrypoint) for Mongo, so that you don't even need to pass `--resources`/`--index-builders`?
