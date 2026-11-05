"""Tests for on-demand price quotes (trip_quotes module + API endpoint).

Covers:
- quote_trip() calls get_flight_price twice and upserts the row
- Second call within freshness window returns cached row without Google call
- One leg None → total None; both present → sum
- get_flight_price raising on one leg → other price still returned
- Endpoint: valid body → 200 with expected fields
- Invalid airport/date → 400
- Scraper RuntimeError → 502
"""
import json
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, '.')

from skybreak.db_migrate import apply_migrations


def _get_client():
    """Create a test Flask client with the app imported fresh."""
    from skybreak.app import app
    app.config['TESTING'] = True
    return app.test_client()


class TestQuoteTrip:
    """Unit tests for the quote_trip function."""

    def test_fresh_quote_calls_get_flight_price_twice(self, clean_db):
        """A fresh quote calls get_flight_price for both legs and upserts the row."""
        from skybreak.trip_quotes import quote_trip

        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = [145.0, 130.0]  # out, ret
            result = quote_trip('FRA', 'CDG', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765')

        assert mock_fp.call_count == 2
        # First call: outbound FRA→CDG
        mock_fp.assert_any_call('FRA', 'CDG', '2026-12-04', 'LH1032')
        # Second call: return CDG→FRA
        mock_fp.assert_any_call('CDG', 'FRA', '2026-12-08', 'AF1765')

        assert result['price_outbound'] == 145.0
        assert result['price_return'] == 130.0
        assert result['price_total'] == 275.0
        assert result['currency'] == 'EUR'
        assert result['cached'] is False

    def test_cached_quote_returns_within_freshness_window(self, clean_db):
        """Second call within freshness window returns cached row without Google call."""
        from skybreak.trip_quotes import quote_trip

        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = [150.0, 140.0]
            # First call — fresh
            result1 = quote_trip('FRA', 'CDG', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765')
            assert result1['cached'] is False

        # Second call — should use DB cache, no get_flight_price calls
        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp2:
            result2 = quote_trip('FRA', 'CDG', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765')

        assert mock_fp2.call_count == 0
        assert result2['cached'] is True
        assert result2['price_outbound'] == 150.0
        assert result2['price_total'] == 290.0

    def test_one_leg_none_total_none(self, clean_db):
        """One leg None → total None; both present → sum."""
        from skybreak.trip_quotes import quote_trip

        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            # Outbound found, return not listed by Google
            mock_fp.side_effect = [145.0, None]
            result = quote_trip('FRA', 'CDG', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765')

        assert result['price_outbound'] == 145.0
        assert result['price_return'] is None
        assert result['price_total'] is None

    def test_both_legs_none(self, clean_db):
        """Both legs not listed → total None."""
        from skybreak.trip_quotes import quote_trip

        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = [None, None]
            result = quote_trip('FRA', 'CDG', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765')

        assert result['price_outbound'] is None
        assert result['price_return'] is None
        assert result['price_total'] is None

    def test_one_leg_exception_other_returns(self, clean_db):
        """get_flight_price raising on one leg → other price still returned."""
        from skybreak.trip_quotes import quote_trip

        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = [RuntimeError("HTTP 502"), 130.0]
            result = quote_trip('FRA', 'CDG', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765')

        assert result['price_outbound'] is None
        assert result['price_return'] == 130.0
        assert result['price_total'] is None  # one leg missing → total None

    def test_requote_same_trip_updates_row(self, clean_db):
        """Re-quoting the same trip updates the DB row (INSERT OR REPLACE).

        Because the first quote's fetched_at is within 1 h, the second call
        returns the cached DB row — this verifies that INSERT OR REPLACE
        actually persisted the first result.
        """
        from skybreak.trip_quotes import quote_trip

        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = [100.0, 90.0]
            r1 = quote_trip('FRA', 'CDG', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765')

        assert r1['price_total'] == 190.0
        assert r1['cached'] is False

        # Second call — should return cached DB row (same key, within 1h)
        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp2:
            r2 = quote_trip('FRA', 'CDG', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765')

        assert mock_fp2.call_count == 0
        assert r2['cached'] is True
        assert r2['price_total'] == 190.0  # same cached value

    def test_uppercase_airports(self, clean_db):
        """Airport codes are uppercased."""
        from skybreak.trip_quotes import quote_trip

        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = [100.0, 90.0]
            quote_trip('fra', 'cdg', '2026-12-04', '2026-12-08', 'lh1032', 'af1765')

        # Verify uppercased codes were used in the DB query (cached lookup)
        from skybreak.db import connect_db
        conn = connect_db()
        row = conn.execute(
            "SELECT start_airport, destination_airport FROM trip_price_quotes LIMIT 1"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == 'FRA'
        assert row[1] == 'CDG'


class TestQuoteEndpoint:
    """Integration tests for the POST /api/prices/quote endpoint."""

    def test_valid_body_returns_200(self, clean_db):
        """Valid body → 200 with expected fields."""
        client = _get_client()
        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = [145.0, 130.0]
            resp = client.post('/api/prices/quote', json={
                'start_airport': 'FRA',
                'destination_airport': 'CDG',
                'outbound_date': '2026-12-04',
                'return_date': '2026-12-08',
                'outbound_flight_number': 'LH1032',
                'return_flight_number': 'AF1765',
            })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['price_outbound'] == 145.0
        assert data['price_return'] == 130.0
        assert data['price_total'] == 275.0
        assert data['currency'] == 'EUR'
        assert 'fetched_at' in data
        assert 'cached' in data

    def test_invalid_airport_returns_400(self, clean_db):
        """Invalid IATA → 400."""
        client = _get_client()
        resp = client.post('/api/prices/quote', json={
            'start_airport': 'XX',
            'destination_airport': 'CDG',
            'outbound_date': '2026-12-04',
            'return_date': '2026-12-08',
            'outbound_flight_number': 'LH1032',
            'return_flight_number': 'AF1765',
        })
        assert resp.status_code == 400

    def test_invalid_date_returns_400(self, clean_db):
        """Invalid date format → 400."""
        client = _get_client()
        resp = client.post('/api/prices/quote', json={
            'start_airport': 'FRA',
            'destination_airport': 'CDG',
            'outbound_date': '04-12-2026',
            'return_date': '2026-12-08',
            'outbound_flight_number': 'LH1032',
            'return_flight_number': 'AF1765',
        })
        assert resp.status_code == 400

    def test_scraper_runtime_error_returns_200_with_null_prices(self, clean_db):
        """Scraper RuntimeError on both legs → 200 with all None prices.

        Per the design: each leg is wrapped in its own try/except so one failure
        doesn't kill the other. RuntimeErrors from get_flight_price are caught
        per-leg and treated as "leg not listed" → None.
        """
        client = _get_client()
        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = RuntimeError("Rate-Limit: after 8 retries")
            resp = client.post('/api/prices/quote', json={
                'start_airport': 'FRA',
                'destination_airport': 'CDG',
                'outbound_date': '2026-12-04',
                'return_date': '2026-12-08',
                'outbound_flight_number': 'LH1032',
                'return_flight_number': 'AF1765',
            })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['price_outbound'] is None
        assert data['price_return'] is None
        assert data['price_total'] is None

    def test_cached_response_returns_200(self, clean_db):
        """Second call within freshness window → 200 with cached=True."""
        client = _get_client()
        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = [145.0, 130.0]
            resp1 = client.post('/api/prices/quote', json={
                'start_airport': 'FRA',
                'destination_airport': 'CDG',
                'outbound_date': '2026-12-04',
                'return_date': '2026-12-08',
                'outbound_flight_number': 'LH1032',
                'return_flight_number': 'AF1765',
            })

        assert resp1.status_code == 200
        assert resp1.get_json()['cached'] is False

        # Second call — cached
        resp2 = client.post('/api/prices/quote', json={
            'start_airport': 'FRA',
            'destination_airport': 'CDG',
            'outbound_date': '2026-12-04',
            'return_date': '2026-12-08',
            'outbound_flight_number': 'LH1032',
            'return_flight_number': 'AF1765',
        })

        assert resp2.status_code == 200
        assert resp2.get_json()['cached'] is True


class TestQuoteEdgeCases:
    """Edge case tests."""

    def test_empty_flight_numbers_no_google_call(self, clean_db):
        """Empty flight numbers → no Google call, all None prices."""
        from skybreak.trip_quotes import quote_trip

        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            result = quote_trip('FRA', 'CDG', '2026-12-04', '2026-12-08', '', '')

        assert mock_fp.call_count == 0
        assert result['price_outbound'] is None
        assert result['price_return'] is None
        assert result['price_total'] is None

    def test_case_insensitive_airport_lookup(self, clean_db):
        """Lowercase airport codes are stored uppercase in DB."""
        from skybreak.trip_quotes import quote_trip

        with patch('skybreak.trip_quotes.get_flight_price') as mock_fp:
            mock_fp.side_effect = [100.0, 90.0]
            quote_trip('fra', 'cdg', '2026-12-04', '2026-12-08', 'LH1032', 'AF1765')

        from skybreak.db import connect_db
        conn = connect_db()
        row = conn.execute(
            "SELECT start_airport, destination_airport FROM trip_price_quotes LIMIT 1"
        ).fetchone()
        conn.close()
        assert row[0] == 'FRA'
        assert row[1] == 'CDG'
