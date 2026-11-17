## TODO:
- on store close, transfer its stocks to another store
- config
- logger
- auth.
- swagger
- separate repositories at line of CQRS
- move asyncpg to db module only, by clean arch.

## Glossary

| Term | Meaning |
| --- | --- |
| Item (артикул) | A product, uniquely identified by its SKU. Can be stocked at one or more FF stores. |
| SKU | The item's article number; unique per item. |
| FF (fulfillment store) | A fulfillment center (склад фулфилмента) that physically holds item stock. In the schema, rows of `stock.stores`. |
| Stock (остатки) | The on-hand quantity of one item at one FF store (row of `stock.stock`). |
| Reserved (резерв) | The part of the stock blocked for FBS orders; always `reserved <= quantity`. |
| Available | `quantity - reserved` — what can be ordered or moved from a store. |
| FBO | Fulfillment via the marketplace: stock leaves the FF and is counted "in transit" to the marketplace warehouse until receipt. |
| FBS | Fulfillment by the seller: the order is shipped directly to the customer; until shipment the stock is reserved at the FF. |
| Inbound (приход) | Stock receipt at an FF — the initial stocking event. |
| Transfer (перемещение) | A stock movement: an FF→FF transfer or a shipment toward an FBO / FBS destination (row of `stock.transfers`). |
| In transit (в пути) | Stock that left its source FF but has not yet been received at the destination. |
| Receipt (приёмка) | Arrival of stock at the destination; marks the transfer as `received`. |
| Transfer log | One row of `stock.transfer_logs` — a single state-change event of a transfer (operation history). |
| Shortage (нехватка) | The chosen FF does not have enough stock, although the total across all FFs is sufficient. |
