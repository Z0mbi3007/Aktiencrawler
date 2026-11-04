import unittest
from tracker import detect_changes
from wikifolio_client import WikifolioClient


class TestPortfolioTracking(unittest.TestCase):
    def setUp(self):
        self.initial_portfolio = {
            "cash_percentage": 10.0,
            "positions": {
                "US0378331005": {
                    "name": "Apple Inc.",
                    "isin": "US0378331005",
                    "percentage": 45.0,
                    "quantity": 100.0,
                    "average_purchase_price": 180.0
                },
                "US5949181045": {
                    "name": "Microsoft Corp.",
                    "isin": "US5949181045",
                    "percentage": 45.0,
                    "quantity": 50.0,
                    "average_purchase_price": 400.0
                }
            }
        }

    def test_no_changes(self):
        changes = detect_changes(self.initial_portfolio, self.initial_portfolio)
        self.assertEqual(len(changes), 0)

    def test_buy_new_position(self):
        updated = {
            "cash_percentage": 5.0,
            "positions": {
                **self.initial_portfolio["positions"],
                "US67066G1040": {
                    "name": "NVIDIA Corp.",
                    "isin": "US67066G1040",
                    "percentage": 20.0,
                    "quantity": 25.0,
                    "average_purchase_price": 120.0
                }
            }
        }
        changes = detect_changes(self.initial_portfolio, updated)
        # Should detect BUY_NEW and CASH_CHANGED
        buy_events = [c for c in changes if c["type"] == "BUY_NEW"]
        self.assertEqual(len(buy_events), 1)
        self.assertEqual(buy_events[0]["isin"], "US67066G1040")
        self.assertEqual(buy_events[0]["percentage"], 20.0)

    def test_sell_position(self):
        updated = {
            "cash_percentage": 55.0,
            "positions": {
                "US0378331005": self.initial_portfolio["positions"]["US0378331005"]
            }
        }
        changes = detect_changes(self.initial_portfolio, updated)
        sell_events = [c for c in changes if c["type"] == "SELL_ALL"]
        self.assertEqual(len(sell_events), 1)
        self.assertEqual(sell_events[0]["isin"], "US5949181045")
        self.assertEqual(sell_events[0]["old_percentage"], 45.0)

    def test_increase_weighting(self):
        updated = {
            "cash_percentage": 5.0,
            "positions": {
                "US0378331005": {
                    "name": "Apple Inc.",
                    "isin": "US0378331005",
                    "percentage": 55.0,
                    "quantity": 120.0,
                    "average_purchase_price": 185.0
                },
                "US5949181045": self.initial_portfolio["positions"]["US5949181045"]
            }
        }
        changes = detect_changes(self.initial_portfolio, updated)
        increase_events = [c for c in changes if c["type"] == "INCREASE"]
        self.assertEqual(len(increase_events), 1)
        self.assertEqual(increase_events[0]["isin"], "US0378331005")
        self.assertEqual(increase_events[0]["new_percentage"], 55.0)

    def test_decrease_weighting(self):
        updated = {
            "cash_percentage": 25.0,
            "positions": {
                "US0378331005": {
                    "name": "Apple Inc.",
                    "isin": "US0378331005",
                    "percentage": 30.0,
                    "quantity": 60.0,
                    "average_purchase_price": 180.0
                },
                "US5949181045": self.initial_portfolio["positions"]["US5949181045"]
            }
        }
        changes = detect_changes(self.initial_portfolio, updated)
        decrease_events = [c for c in changes if c["type"] == "DECREASE"]
        self.assertEqual(len(decrease_events), 1)
        self.assertEqual(decrease_events[0]["isin"], "US0378331005")
        self.assertEqual(decrease_events[0]["new_percentage"], 30.0)

    def test_parse_portfolio(self):
        client = WikifolioClient(email="test@example.com", password="dummy")
        sample_raw = {
            "groups": [
                {
                    "type": 0,
                    "items": [
                        {"name": "Cash", "isin": "", "percentage": 15.5}
                    ]
                },
                {
                    "type": 1,
                    "items": [
                        {
                            "name": "Tesla Inc.",
                            "isin": "US88160R1014",
                            "percentage": 84.5,
                            "quantity": 10.0,
                            "averagePurchasePrice": 220.0,
                            "close": 235.0,
                            "performanceSinceBuy": 6.82
                        }
                    ]
                }
            ]
        }
        parsed = client._parse_portfolio(sample_raw)
        self.assertEqual(parsed["cash_percentage"], 15.5)
        self.assertIn("US88160R1014", parsed["positions"])
        self.assertEqual(parsed["positions"]["US88160R1014"]["percentage"], 84.5)


    def test_market_hours_filter(self):
        import config
        # When MARKET_HOURS_ONLY is False, should always be open
        config.MARKET_HOURS_ONLY = False
        self.assertTrue(config.is_market_open())

    def test_simulator_engine_pipeline(self):
        import numpy as np
        import pandas as pd
        from simulator_engine import (
            calculate_technical_indicators,
            evaluate_risk_and_rating,
            simulate_future_scenarios,
            generate_advisory_report,
            resolve_query_to_ticker,
        )

        # ISIN mapping check
        self.assertEqual(resolve_query_to_ticker("US0378331005"), "AAPL")
        self.assertEqual(resolve_query_to_ticker("NVDA"), "NVDA")

        # Synthetische 250-Tage OHLCV Historie erzeugen
        dates = pd.bdate_range("2025-01-01", periods=250)
        rng = np.random.default_rng(123)
        close_prices = 100.0 * np.cumprod(1.0 + rng.normal(0.0008, 0.015, size=250))
        df = pd.DataFrame(
            {
                "Open": close_prices * 0.995,
                "High": close_prices * 1.012,
                "Low": close_prices * 0.988,
                "Close": close_prices,
                "Volume": rng.integers(1_000_000, 5_000_000, size=250),
            },
            index=dates,
        )

        mock_info = {
            "beta": 1.05,
            "debtToEquity": 45.0,
            "currentRatio": 1.8,
            "profitMargins": 0.24,
            "returnOnEquity": 0.32,
            "freeCashflow": 50_000_000_000,
            "totalCash": 60_000_000_000,
            "totalDebt": 40_000_000_000,
            "marketCap": 2_500_000_000_000,
            "targetMeanPrice": float(close_prices[-1] * 1.15),
            "numberOfAnalystOpinions": 28,
        }

        tech = calculate_technical_indicators(df)
        self.assertIn("tech_score", tech)
        self.assertTrue(0 <= tech["tech_score"] <= 100)
        self.assertGreater(len(tech["signals"]), 0)

        risk = evaluate_risk_and_rating(df, mock_info)
        self.assertEqual(risk["rating_grade"], "AAA")
        self.assertGreaterEqual(risk["rating_score"], 86.0)

        sim = simulate_future_scenarios(df, tech, risk, horizon_days=63, num_simulations=100)
        self.assertEqual(len(sim["future_dates"]), 64)
        self.assertGreater(sim["summary"]["bull_price"], sim["summary"]["bear_price"])

        adv = generate_advisory_report("AAPL", mock_info, tech, risk, sim)
        self.assertIn("composite_score", adv)
        self.assertIn("verdict", adv)
        self.assertIn("tactical_levels", adv)

        # Chart-Builder aus dashboard.py testen
        from dashboard import build_technical_chart, build_simulation_chart
        fig_tech = build_technical_chart(tech["df"], tech, "AAPL", "USD", True, True, True, True)
        self.assertIsNotNone(fig_tech)
        fig_sim = build_simulation_chart(df, sim, risk, "AAPL", "USD")
        self.assertIsNotNone(fig_sim)




if __name__ == "__main__":
    unittest.main()
