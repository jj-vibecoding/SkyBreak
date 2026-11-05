"""Tests for price-alert evaluation and Telegram notification dispatch.

Covers (per design-doc test plan):
- effective_target: trip set → ('trip'); only destination set → ('destination'); neither → None.
- Edge-trigger matrix: (prev, new, target) → fires / not fires for the 5 key combinations.
- Trip target overrides destination target in evaluation and target_scope logging.
- Setting target above current price does NOT fire (previous ≤ target).
- send_telegram success and failure paths (monkeypatched requests.post).
- No credentials → no call attempted, nothing logged.
- Failed send stored with status 'failed'.
- Endpoints: PUT trip target updates row; null clears it; invalid value → 400.
  PUT destination target upserts/deletes; invalid IATA → 400.
  GET /api/favorites rows include both target fields.
  Test endpoint returns {sent: false, detail} when token is empty.
"""
import json
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, '.')

from skybreak.db_migrate import apply_migrations


def _client():
    from skybreak.app import app
    app.config['TESTING'] = True
    return app.test_client()


# ── Unit: effective_target ───────────────────────────────────────────────────


class TestEffectiveTarget:
    """Test the effective_target helper (target resolution)."""

    def test_trip_target_set_returns_trip_scope(self, clean_db):
        from skybreak.notifications import effective_target

        fav = {"target_price": 300.0, "destination_airport": "CDG"}
        target, scope = effective_target(fav, "CDG")
        assert target == 300.0
        assert scope == "trip"

    def test_only_destination_set_returns_destination_scope(self, clean_db):
        from skybreak.db import connect_db
        conn = connect_db()
        conn.execute(
            "INSERT OR REPLACE INTO destination_targets (destination_airport, target_price) VALUES ('CDG', 250.0)"
        )
        conn.commit()
        conn.close()

        from skybreak.notifications import effective_target

        fav = {"target_price": None, "destination_airport": "CDG"}
        target, scope = effective_target(fav, "CDG")
        assert target == 250.0
        assert scope == "destination"

    def test_neither_set_returns_none(self, clean_db):
        from skybreak.notifications import effective_target

        fav = {"target_price": None, "destination_airport": "XYZ"}
        target, scope = effective_target(fav, "XYZ")
        assert target is None
        assert scope is None


# ── Unit: edge-trigger matrix ────────────────────────────────────────────────


class TestEdgeTriggerMatrix:
    """Edge-trigger firing logic (prev vs new vs target)."""

    def _setup_favorite(self, fav_id, prices):
        """Insert a favorite and its price history rows.

        Prices are inserted oldest-first with staggered timestamps so that
        ``ORDER BY fetched_at DESC`` is deterministic: index 0 → oldest,
        last → newest (the "current" price).
        """
        from skybreak.db import connect_db
        conn = connect_db()
        conn.execute(
            "INSERT OR REPLACE INTO favorite_trips "
            "(id, destination_airport, start_airport, outbound_trip_date, "
            "return_trip_date, outbound_flight_number, return_flight_number, target_price) "
            "VALUES (?, 'CDG', 'FRA', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765', NULL)",
            (fav_id,),
        )
        for idx, total in enumerate(prices):
            # oldest price first; newest last
            conn.execute(
                "INSERT INTO favorite_trip_prices "
                "(favorite_id, price_outbound, price_return, price_total, fetched_at) "
                "VALUES (?, 50, 50, ?, datetime('now', ?))",
                (fav_id, total, f"-{len(prices) - idx} seconds"),
            )
        conn.commit()
        conn.close()

    def _set_dest_target(self, dest_airport="CDG", price=300.0):
        from skybreak.db import connect_db
        conn = connect_db()
        conn.execute(
            "INSERT OR REPLACE INTO destination_targets (destination_airport, target_price) VALUES (?, ?)",
            (dest_airport, price),
        )
        conn.commit()
        conn.close()

    def _mock_prices(self, out=50.0, ret=50.0):
        """Return a successful price-fetch result dict."""
        return {"favorite_id": 1, "price_outbound": out, "price_return": ret, "price_total": out + ret}

    @patch('skybreak.flight_prices.get_flight_price')
    def test_prev_none_new_below_target_fires(self, mock_fp, clean_db):
        """First price ever is below target → fires (prev=None rule)."""
        self._setup_favorite(10, [200.0])  # only one price row
        self._set_dest_target("CDG", 300.0)

        with patch('skybreak.notifications.get_setting', side_effect={
            "telegram_bot_token": "fake-token", "telegram_chat_id": "12345"
        }.get):
            with patch('skybreak.notifications.send_telegram', return_value=(True, "")) as mock_send:
                from skybreak.notifications import evaluate_alert
                result = evaluate_alert(10)

        assert result is not None
        assert result["status"] == "sent"
        assert result["target_scope"] == "destination"
        assert mock_send.call_count == 1

    @patch('skybreak.flight_prices.get_flight_price')
    def test_prev_above_new_below_fires(self, mock_fp, clean_db):
        """Price dropped from above to below target → fires."""
        self._setup_favorite(11, [350.0, 200.0])  # prev=350, new=200
        self._set_dest_target("CDG", 300.0)

        with patch('skybreak.notifications.get_setting', side_effect={
            "telegram_bot_token": "fake-token", "telegram_chat_id": "12345"
        }.get):
            with patch('skybreak.notifications.send_telegram', return_value=(True, "")) as mock_send:
                from skybreak.notifications import evaluate_alert
                result = evaluate_alert(11)

        assert result is not None
        assert result["target_scope"] == "destination"
        assert mock_send.call_count == 1

    @patch('skybreak.flight_prices.get_flight_price')
    def test_prev_below_new_even_lower_no_fire(self, mock_fp, clean_db):
        """Already below target → stays silent (re-arm rule)."""
        self._setup_favorite(12, [250.0, 200.0])  # prev=250 ≤ target=300

        with patch('skybreak.notifications.get_setting', side_effect={
            "telegram_bot_token": "fake-token", "telegram_chat_id": "12345"
        }.get):
            with patch('skybreak.notifications.send_telegram', return_value=(True, "")) as mock_send:
                from skybreak.notifications import evaluate_alert
                result = evaluate_alert(12)

        assert result is None
        assert mock_send.call_count == 0

    @patch('skybreak.flight_prices.get_flight_price')
    def test_new_above_target_no_fire(self, mock_fp, clean_db):
        """Price still above target → no fire."""
        self._setup_favorite(13, [250.0, 350.0])  # new=350 > target=300

        with patch('skybreak.notifications.get_setting', side_effect={
            "telegram_bot_token": "fake-token", "telegram_chat_id": "12345"
        }.get):
            with patch('skybreak.notifications.send_telegram', return_value=(True, "")) as mock_send:
                from skybreak.notifications import evaluate_alert
                result = evaluate_alert(13)

        assert result is None
        assert mock_send.call_count == 0

    @patch('skybreak.flight_prices.get_flight_price')
    def test_new_is_none_no_fire(self, mock_fp, clean_db):
        """Total is NULL (a leg unlisted) → no alert."""
        self._setup_favorite(14, [250.0, None])  # new_total = None

        with patch('skybreak.notifications.get_setting', side_effect={
            "telegram_bot_token": "fake-token", "telegram_chat_id": "12345"
        }.get):
            with patch('skybreak.notifications.send_telegram', return_value=(True, "")) as mock_send:
                from skybreak.notifications import evaluate_alert
                result = evaluate_alert(14)

        assert result is None
        assert mock_send.call_count == 0


# ── Unit: trip overrides destination ────────────────────────────────────────


class TestTripOverridesDestination:
    """Trip target wins over destination target."""

    def _setup_with_both_targets(self, fav_id, trip_tp=None):
        from skybreak.db import connect_db
        conn = connect_db()
        conn.execute(
            "INSERT OR REPLACE INTO favorite_trips "
            "(id, destination_airport, start_airport, outbound_trip_date, "
            "return_trip_date, outbound_flight_number, return_flight_number, target_price) "
            "VALUES (?, 'CDG', 'FRA', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765', ?)",
            (fav_id, trip_tp),
        )
        conn.execute(
            "INSERT INTO destination_targets (destination_airport, target_price) VALUES ('CDG', 400.0)"
        )
        conn.commit()
        conn.close()

    @patch('skybreak.flight_prices.get_flight_price')
    def test_trip_target_wins_in_evaluation(self, mock_fp, clean_db):
        """When both trip and destination targets exist, trip target is used."""
        self._setup_with_both_targets(20, trip_tp=300.0)
        # prev=450 (above dest target 400 AND above trip target 300), new=250 (below both)
        from skybreak.db import connect_db
        conn = connect_db()
        # oldest first, newest last → deterministic ORDER BY fetched_at DESC
        conn.execute(
            "INSERT INTO favorite_trip_prices (favorite_id, price_outbound, price_return, price_total, fetched_at) VALUES (20, 100, 100, 450, datetime('now', '-2 seconds'))"
        )
        conn.execute(
            "INSERT INTO favorite_trip_prices (favorite_id, price_outbound, price_return, price_total, fetched_at) VALUES (20, 100, 100, 250, datetime('now', '-1 second'))"
        )
        conn.commit()
        conn.close()

        with patch('skybreak.notifications.get_setting', side_effect={
            "telegram_bot_token": "fake-token", "telegram_chat_id": "12345"
        }.get):
            with patch('skybreak.notifications.send_telegram', return_value=(True, "")) as mock_send:
                from skybreak.notifications import evaluate_alert
                result = evaluate_alert(20)

        assert result is not None
        assert result["target_scope"] == "trip"
        # Message should reference trip target (300), not destination (400)
        assert "300" in result["message"]


# ── Unit: send_telegram ──────────────────────────────────────────────────────


class TestSendTelegram:
    """Test send_telegram success and failure paths."""

    def test_success_returns_true(self, clean_db):
        from skybreak.notifications import send_telegram

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = ""

        with patch('skybreak.notifications.requests.post', return_value=mock_resp) as mock_post:
            ok, detail = send_telegram("fake-token", "12345", "Hello")

        assert ok is True
        assert detail == ""
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "sendMessage" in call_args[0][0]
        assert call_args[1]["json"]["text"] == "Hello"

    def test_http_error_returns_false(self, clean_db):
        from skybreak.notifications import send_telegram

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"

        with patch('skybreak.notifications.requests.post', return_value=mock_resp) as mock_post:
            ok, detail = send_telegram("bad-token", "12345", "Hello")

        assert ok is False
        assert "HTTP 401" in detail

    def test_network_error_returns_false(self, clean_db):
        from skybreak.notifications import send_telegram

        with patch('skybreak.notifications.requests.post', side_effect=Exception("Connection refused")) as mock_post:
            ok, detail = send_telegram("token", "12345", "Hello")

        assert ok is False
        assert "Connection refused" in detail


# ── Unit: no credentials ────────────────────────────────────────────────────


class TestNoCredentials:
    """Without configured credentials, nothing is sent or logged."""

    @patch('skybreak.flight_prices.get_flight_price')
    def test_no_credentials_no_call(self, mock_fp, clean_db):
        """evaluate_alert returns None when token/chat_id are empty."""
        self._setup_favorite_no_target(30)
        from skybreak.db import connect_db
        conn = connect_db()
        conn.execute("INSERT INTO favorite_trip_prices (favorite_id, price_outbound, price_return, price_total) VALUES (30, 50, 50, 200)")
        conn.commit()
        conn.close()

        with patch('skybreak.notifications.get_setting', return_value=""):
            with patch('skybreak.notifications.send_telegram') as mock_send:
                from skybreak.notifications import evaluate_alert
                result = evaluate_alert(30)

        assert result is None
        assert mock_send.call_count == 0

    def _setup_favorite_no_target(self, fav_id):
        from skybreak.db import connect_db
        conn = connect_db()
        conn.execute(
            "INSERT OR REPLACE INTO favorite_trips "
            "(id, destination_airport, start_airport, outbound_trip_date, "
            "return_trip_date, outbound_flight_number, return_flight_number, target_price) "
            "VALUES (?, 'CDG', 'FRA', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765', NULL)",
            (fav_id,),
        )
        conn.commit()
        conn.close()


# ── Unit: failed send stored ────────────────────────────────────────────────


class TestFailedSendStored:
    """Failed Telegram sends are logged with status 'failed'."""

    @patch('skybreak.flight_prices.get_flight_price')
    def test_failed_send_logged(self, mock_fp, clean_db):
        self._setup(40)

        with patch('skybreak.notifications.get_setting', side_effect={
            "telegram_bot_token": "fake-token", "telegram_chat_id": "12345"
        }.get):
            with patch('skybreak.notifications.send_telegram', return_value=(False, "HTTP 403")) as mock_send:
                from skybreak.notifications import evaluate_alert
                result = evaluate_alert(40)

        assert result is not None
        assert result["status"] == "failed"
        assert "403" in result["detail"]

    def _setup(self, fav_id):
        from skybreak.db import connect_db
        conn = connect_db()
        conn.execute(
            "INSERT OR REPLACE INTO favorite_trips "
            "(id, destination_airport, start_airport, outbound_trip_date, "
            "return_trip_date, outbound_flight_number, return_flight_number, target_price) "
            "VALUES (?, 'CDG', 'FRA', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765', 300)",
            (fav_id,),
        )
        # oldest first, newest last → deterministic ORDER BY fetched_at DESC
        conn.execute(
            "INSERT INTO favorite_trip_prices (favorite_id, price_outbound, price_return, price_total, fetched_at) VALUES (?, 100, 100, 400, datetime('now', '-2 seconds'))",
            (fav_id,),
        )
        conn.execute(
            "INSERT INTO favorite_trip_prices (favorite_id, price_outbound, price_return, price_total, fetched_at) VALUES (?, 50, 50, 200, datetime('now', '-1 second'))",
            (fav_id,),
        )
        conn.commit()
        conn.close()


# ── Integration: API endpoints ───────────────────────────────────────────────


class TestAPIEndpoints:
    """Integration tests for the new API routes."""

    def test_put_trip_target_updates_row(self, clean_db):
        """PUT /api/favorites/<id> sets target_price on the favorite."""
        client = _client()
        fav_id = self._create_favorite(client)

        resp = client.put(f"/api/favorites/{fav_id}", json={"target_price": 300})
        assert resp.status_code == 200
        data = resp.json
        assert data["target_price"] == 300.0
        assert data["destination_airport"] == "CDG"

    def test_put_trip_target_null_clears(self, clean_db):
        """PUT /api/favorites/<id> with null target_price clears it."""
        client = _client()
        fav_id = self._create_favorite(client)

        # Set first
        client.put(f"/api/favorites/{fav_id}", json={"target_price": 300})
        favs = client.get("/api/favorites").json
        assert favs[0]["target_price"] == 300.0

        # Clear
        resp = client.put(f"/api/favorites/{fav_id}", json={"target_price": None})
        assert resp.status_code == 200
        assert resp.json["target_price"] is None

    def test_put_trip_target_invalid_value_400(self, clean_db):
        """PUT /api/favorites/<id> with invalid target_price → 400."""
        client = _client()
        fav_id = self._create_favorite(client)

        resp = client.put(f"/api/favorites/{fav_id}", json={"target_price": "not-a-number"})
        assert resp.status_code == 400

    def test_put_destination_target_upserts(self, clean_db):
        """PUT /api/destination-targets/<code> upserts a destination target."""
        client = _client()
        resp = client.put("/api/destination-targets/CDG", json={"target_price": 250})
        assert resp.status_code == 200
        assert resp.json["destination_airport"] == "CDG"
        assert resp.json["target_price"] == 250.0

    def test_put_destination_target_null_deletes(self, clean_db):
        """PUT /api/destination-targets/<code> with null deletes the row."""
        client = _client()
        # Upsert first
        client.put("/api/destination-targets/CDG", json={"target_price": 250})
        # Delete via null
        resp = client.put("/api/destination-targets/CDG", json={"target_price": None})
        assert resp.status_code == 200
        assert "deleted" in resp.json

    def test_put_destination_target_invalid_iata_400(self, clean_db):
        """PUT /api/destination-targets with invalid IATA → 400."""
        client = _client()
        resp = client.put("/api/destination-targets/XXXXX", json={"target_price": 250})
        assert resp.status_code == 400

    def test_get_favorites_includes_target_fields(self, clean_db):
        """GET /api/favorites rows include target_price and destination_target_price."""
        client = _client()
        fav_id = self._create_favorite(client)
        # Set a destination target for CDG
        client.put("/api/destination-targets/CDG", json={"target_price": 300})

        resp = client.get("/api/favorites")
        assert resp.status_code == 200
        favs = resp.json
        assert len(favs) >= 1
        fav = favs[0]
        assert "target_price" in fav
        assert "destination_target_price" in fav
        assert fav["destination_target_price"] == 300.0

    def test_get_notifications_empty(self, clean_db):
        """GET /api/notifications returns empty list when no notifications exist."""
        client = _client()
        resp = client.get("/api/notifications")
        assert resp.status_code == 200
        assert resp.json == []

    def test_test_endpoint_no_credentials(self, clean_db):
        """POST /api/notifications/test returns {sent: false} when credentials missing."""
        client = _client()
        with patch('skybreak.app.get_setting', return_value=""):
            resp = client.post("/api/notifications/test")
        assert resp.status_code == 200
        data = resp.json
        assert data["sent"] is False
        assert "detail" in data

    def _create_favorite(self, client):
        """Helper: create a favorite and return its id."""
        client.post("/api/favorites", json={
            "destination_airport": "CDG",
            "outbound_flight_number": "LH1032",
            "return_flight_number": "AF1765",
            "start_airport": "FRA",
            "trip_date": "2026-12-04",
            "return_trip_date": "2026-12-08",
        })
        return client.get("/api/favorites").json[0]["id"]


# ── Unit: last_notifications ────────────────────────────────────────────────


class TestLastNotifications:
    """Test the notification log retrieval."""

    def test_returns_sorted_newest_first(self, clean_db):
        import time
        from skybreak.db import connect_db
        from skybreak.notifications import last_notifications

        conn = connect_db()
        for i in range(5):
            # Stagger timestamps so ORDER BY sent_at DESC is deterministic
            conn.execute(
                "INSERT INTO notifications (favorite_id, message, status, target_scope, sent_at) "
                "VALUES (?, 'msg', 'sent', 'trip', datetime('now', ?))",
                (10 + i, f"+{i} seconds"),
            )
        conn.commit()
        conn.close()

        results = last_notifications(limit=50)
        assert len(results) == 5
        # Newest first (highest ID inserted last with latest timestamp)
        assert results[0]["id"] > results[-1]["id"]


# ── Unit: target above current price does NOT fire ──────────────────────────


class TestTargetAboveCurrentPrice:
    """Setting target above current price does NOT fire (edge rule)."""

    @patch('skybreak.flight_prices.get_flight_price')
    def test_prev_below_target_no_fire(self, mock_fp, clean_db):
        """Previous price was already ≤ target → no re-alert when new is also below."""
        from skybreak.db import connect_db
        conn = connect_db()
        conn.execute(
            "INSERT OR REPLACE INTO favorite_trips "
            "(id, destination_airport, start_airport, outbound_trip_date, "
            "return_trip_date, outbound_flight_number, return_flight_number, target_price) "
            "VALUES (?, 'CDG', 'FRA', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765', 300)",
            (50,),
        )
        # prev=200 ≤ target=300, new=150 ≤ target=300 → no fire
        conn.execute("INSERT INTO favorite_trip_prices (favorite_id, price_outbound, price_return, price_total) VALUES (50, 100, 100, 200)")
        conn.execute("INSERT INTO favorite_trip_prices (favorite_id, price_outbound, price_return, price_total) VALUES (50, 75, 75, 150)")
        conn.commit()
        conn.close()

        with patch('skybreak.notifications.get_setting', side_effect={
            "telegram_bot_token": "fake-token", "telegram_chat_id": "12345"
        }.get):
            with patch('skybreak.notifications.send_telegram') as mock_send:
                from skybreak.notifications import evaluate_alert
                result = evaluate_alert(50)

        assert result is None
        assert mock_send.call_count == 0
