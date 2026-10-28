import unittest
from src.engine.modes import ModeClassifier

class TestModeClassifier(unittest.TestCase):
    def test_delta_classification(self):
        # High buy delta ratio >= 0.15
        color, delta, ratio = ModeClassifier.classify_delta(buy_vol=80.0, sell_vol=20.0, total_vol=100.0)
        self.assertEqual(color, 'delta_buy')
        self.assertEqual(delta, 60.0)
        self.assertAlmostEqual(ratio, 0.60)

        # High sell delta ratio <= -0.15
        color, delta, ratio = ModeClassifier.classify_delta(buy_vol=20.0, sell_vol=80.0, total_vol=100.0)
        self.assertEqual(color, 'delta_sell')
        self.assertEqual(delta, -60.0)
        self.assertAlmostEqual(ratio, -0.60)

        # Balanced / Neutral
        color, delta, ratio = ModeClassifier.classify_delta(buy_vol=52.0, sell_vol=48.0, total_vol=100.0)
        self.assertEqual(color, 'delta_neutral')

    def test_diagonal_imbalance_micro(self):
        cells = [
            # time bucket 0, price 10
            {'t_idx': 0, 'p_idx': 10, 'buy_vol': 30.0, 'sell_vol': 2.0, 'volume': 32.0, 'tick_count': 5},
            # time bucket 0, price 9 (directly below price 10)
            {'t_idx': 0, 'p_idx': 9,  'buy_vol': 4.0,  'sell_vol': 5.0, 'volume': 9.0,  'tick_count': 2},
            # time bucket 0, price 11 (directly above price 10)
            {'t_idx': 0, 'p_idx': 11, 'buy_vol': 25.0, 'sell_vol': 1.0, 'volume': 26.0, 'tick_count': 4}
        ]

        imb_map = ModeClassifier.compute_micro_diagonal_imbalances(cells, ratio=3.0, min_vol=5.0)

        # At (0, 10): buy_vol is 30.0, diagonal sell at (0, 9) is 5.0 -> ratio 30/5 = 6.0 >= 3.0 -> BUY IMBALANCE
        self.assertEqual(imb_map[(0, 10)]['imb_type'], 'imb_buy')

        # At (0, 11): buy_vol is 25.0, diagonal sell at (0, 10) is 2.0 -> ratio 25/2 = 12.5 >= 3.0 -> BUY IMBALANCE
        self.assertEqual(imb_map[(0, 11)]['imb_type'], 'imb_buy')

        # Consecutive levels (10 and 11) have buy imbalance -> stack glow should be True!
        self.assertTrue(imb_map[(0, 10)]['has_stack'])
        self.assertTrue(imb_map[(0, 11)]['has_stack'])

if __name__ == "__main__":
    unittest.main()
