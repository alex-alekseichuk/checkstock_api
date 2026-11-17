"""E2E tests for the stock report endpoints (``GET /stock/``, ``GET /stock/in_transit``)."""

from fastapi.testclient import TestClient


def _store(client: TestClient, title: str) -> dict:
    response = client.post("/stores/", json={"title": title})
    assert response.status_code == 201
    return response.json()


def _item(client: TestClient, sku: str, title: str = "Item") -> dict:
    response = client.post("/items/", json={"sku": sku, "title": title})
    assert response.status_code == 201
    return response.json()


def _inbound(client: TestClient, store_id: str, sku: str, quantity: int) -> dict:
    response = client.post(
        "/transfers/",
        json={"type": "inbound", "dest_store_id": store_id, "sku": sku, "quantity": quantity},
    )
    assert response.status_code == 201
    return response.json()


def _transfer(client: TestClient, source_id: str, dest_id: str, sku: str, quantity: int) -> dict:
    response = client.post(
        "/transfers/",
        json={
            "type": "transfer",
            "source_store_id": source_id,
            "dest_store_id": dest_id,
            "sku": sku,
            "quantity": quantity,
        },
    )
    assert response.status_code == 201
    return response.json()


def _ship(client: TestClient, transfer_type: str, source_id: str, sku: str, quantity: int) -> dict:
    response = client.post(
        "/transfers/",
        json={"type": transfer_type, "source_store_id": source_id, "sku": sku, "quantity": quantity},
    )
    assert response.status_code == 201
    return response.json()


def test_list_stock_is_empty_on_fresh_db(client: TestClient) -> None:
    assert client.get("/stock/").json() == []


def test_inbound_appears_in_stock(client: TestClient) -> None:
    store = _store(client, "Север")
    item = _item(client, "SKU-101", "Органайзер")
    _inbound(client, store["id"], "SKU-101", 10)

    rows = client.get("/stock/").json()

    assert rows == [
        {
            "item_id": item["id"],
            "item_sku": "SKU-101",
            "item_title": "Органайзер",
            "store_id": store["id"],
            "store_title": "Север",
            "quantity": 10,
            "reserved": 0,
            "available": 10,
        }
    ]


def test_stock_is_sorted_by_sku_then_store_title(client: TestClient) -> None:
    store_a = _store(client, "A")
    store_b = _store(client, "B")
    item_1 = _item(client, "SKU-101")
    item_2 = _item(client, "SKU-102")

    _inbound(client, store_a["id"], "SKU-102", 1)
    _inbound(client, store_b["id"], "SKU-102", 2)
    _inbound(client, store_a["id"], "SKU-101", 3)

    rows = client.get("/stock/").json()

    assert [(row["item_sku"], row["store_title"]) for row in rows] == [
        ("SKU-101", "A"),
        ("SKU-102", "A"),
        ("SKU-102", "B"),
    ]
    assert [row["quantity"] for row in rows] == [3, 1, 2]


def test_fbs_reservation_reduces_available(client: TestClient) -> None:
    store = _store(client, "Север")
    _item(client, "SKU-101")
    _inbound(client, store["id"], "SKU-101", 10)
    _ship(client, "ship_fbs", store["id"], "SKU-101", 4)

    rows = client.get("/stock/").json()

    assert rows[0]["quantity"] == 10
    assert rows[0]["reserved"] == 4
    assert rows[0]["available"] == 6


def test_transfer_splits_stock_between_stores(client: TestClient) -> None:
    store_a = _store(client, "Север")
    store_b = _store(client, "Юг")
    _item(client, "SKU-101")
    _inbound(client, store_a["id"], "SKU-101", 10)
    _transfer(client, store_a["id"], store_b["id"], "SKU-101", 4)

    rows = client.get("/stock/").json()

    # The goods are in transit: the destination has no stock yet.
    assert [(row["store_id"], row["quantity"]) for row in rows] == [(store_a["id"], 6)]


def test_full_transfer_out_drains_source_from_listing(client: TestClient) -> None:
    store_a = _store(client, "Север")
    store_b = _store(client, "Юг")
    _item(client, "SKU-101")
    _inbound(client, store_a["id"], "SKU-101", 5)
    transfer = _transfer(client, store_a["id"], store_b["id"], "SKU-101", 5)
    response = client.post(f"/transfers/{transfer['id']}/receive")
    assert response.status_code == 200

    rows = client.get("/stock/").json()

    # The source is now empty (quantity > 0 filter) and only the destination is listed.
    assert [(row["store_id"], row["quantity"]) for row in rows] == [(store_b["id"], 5)]


def test_list_in_transit_is_empty_on_fresh_db(client: TestClient) -> None:
    assert client.get("/stock/in_transit").json() == []


def test_transfer_in_transit_entry(client: TestClient) -> None:
    store_a = _store(client, "Север")
    store_b = _store(client, "Юг")
    item = _item(client, "SKU-101", "Органайзер")
    _inbound(client, store_a["id"], "SKU-101", 10)
    _transfer(client, store_a["id"], store_b["id"], "SKU-101", 4)

    rows = client.get("/stock/in_transit").json()

    assert [row["item_id"] for row in rows] == [item["id"]]
    row = rows[0]
    assert row["item_sku"] == "SKU-101"
    assert row["item_title"] == "Органайзер"
    assert row["source_store_id"] == store_a["id"]
    assert row["source_store_title"] == "Север"
    assert row["dest_store_id"] == store_b["id"]
    assert row["dest_store_title"] == "Юг"
    assert row["quantity"] == 4
    assert row["type"] == "transfer"
    assert row["departed_at"]


def test_fbo_in_transit_entry_has_no_destination(client: TestClient) -> None:
    store_a = _store(client, "Север")
    _item(client, "SKU-101")
    _inbound(client, store_a["id"], "SKU-101", 10)
    _ship(client, "ship_fbo", store_a["id"], "SKU-101", 3)

    rows = client.get("/stock/in_transit").json()

    assert len(rows) == 1
    row = rows[0]
    assert row["source_store_id"] == store_a["id"]
    assert row["dest_store_id"] is None
    assert row["dest_store_title"] is None
    assert row["quantity"] == 3
    assert row["type"] == "ship_fbo"


def test_fbs_in_transit_after_approve(client: TestClient) -> None:
    store_a = _store(client, "Север")
    _item(client, "SKU-101")
    _inbound(client, store_a["id"], "SKU-101", 10)
    transfer = _ship(client, "ship_fbs", store_a["id"], "SKU-101", 4)
    response = client.post(f"/transfers/{transfer['id']}/approve")
    assert response.status_code == 200

    rows = client.get("/stock/in_transit").json()

    assert len(rows) == 1
    row = rows[0]
    assert row["source_store_id"] == store_a["id"]
    assert row["dest_store_id"] is None
    assert row["quantity"] == 4
    assert row["type"] == "ship_fbs"


def test_received_transfer_disappears_from_in_transit(client: TestClient) -> None:
    store_a = _store(client, "Север")
    store_b = _store(client, "Юг")
    _item(client, "SKU-101")
    _inbound(client, store_a["id"], "SKU-101", 10)
    transfer = _transfer(client, store_a["id"], store_b["id"], "SKU-101", 4)
    response = client.post(f"/transfers/{transfer['id']}/receive")
    assert response.status_code == 200

    assert client.get("/stock/in_transit").json() == []


def test_in_transit_filter_by_type(client: TestClient) -> None:
    store_a = _store(client, "Север")
    store_b = _store(client, "Юг")
    _item(client, "SKU-101")
    _inbound(client, store_a["id"], "SKU-101", 10)
    _transfer(client, store_a["id"], store_b["id"], "SKU-101", 2)
    _ship(client, "ship_fbo", store_a["id"], "SKU-101", 3)
    fbs = _ship(client, "ship_fbs", store_a["id"], "SKU-101", 4)
    response = client.post(f"/transfers/{fbs['id']}/approve")
    assert response.status_code == 200

    def types(url: str) -> list[str]:
        return [row["type"] for row in client.get(url).json()]

    assert types("/stock/in_transit") == ["transfer", "ship_fbo", "ship_fbs"]
    assert types("/stock/in_transit?type=transfer") == ["transfer"]
    assert types("/stock/in_transit?type=ship_fbo") == ["ship_fbo"]
    assert types("/stock/in_transit?type=ship_fbs") == ["ship_fbs"]


def test_in_transit_rejects_inbound_filter(client: TestClient) -> None:
    assert client.get("/stock/in_transit?type=inbound").status_code == 422
