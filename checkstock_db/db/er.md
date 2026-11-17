# ER diagram

All tables live in the `stock` schema. Custom enum types:

- `store_status`: `active`, `closed`
- `transfer_type`: `inbound`, `transfer`, `ship_fbo`, `ship_fbs`
- `transfer_status`: `reserved`, `canceled`, `in_transit`, `received`
- `transfer_event`: `inbound`, `shipped`, `received`, `reserved`, `canceled`

```mermaid
erDiagram
    items ||--o{ stock : "остатки товаров"
    stores ||--o{ stock : "находятся в FF store"
    items ||--o{ transfers : "перемещается"
    stores ||--o{ transfers : "перемещается из"
    stores ||--o{ transfers : "перемещается в"
    transfers ||--|{ transfer_logs : "изменяет состояние"

    items {
        uuid id PK
        text sku UK
        text title
        timestamptz created_at
    }

    stores {
        uuid id PK
        text title
        store_status status
        timestamptz created_at
    }

    stock {
        uuid item_id PK,FK
        uuid stock_id PK,FK
        integer quantity
        integer reserved
        timestamptz created_at
    }

    transfers {
        uuid id PK
        uuid item_id FK
        integer quantity
        transfer_type type
        uuid src_stock_id FK
        uuid dest_stock_id FK
        transfer_status status
        timestamptz created_at
        timestamptz updated_at
    }

    transfer_logs {
        integer id PK
        uuid transfer_id FK
        transfer_event event
        timestamptz logged_at
    }
```
