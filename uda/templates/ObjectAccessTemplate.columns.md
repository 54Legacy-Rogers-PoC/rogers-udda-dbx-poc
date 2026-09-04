# Object Access Template Columns

Use these column headers exactly in worksheet `ObjectAccess` (or CSV header row):

- Object Type
- Activity
- Catalog Name
- Schema Name
- Object Name
- Folder Path
- Privileges

## Rules
- `Object Type`: catalog | schema | view | folder
- `Activity`: ADD | REMOVE (if empty, request-level activity_type is used)
- `Privileges`: comma-separated list, for example `USE_SCHEMA,SELECT`
- `Folder Path`: required only when Object Type is folder
- `Catalog Name`: required for catalog, schema, and view
- `Schema Name`: required for schema and view
- `Object Name`: required for view
