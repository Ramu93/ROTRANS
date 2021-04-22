import unittest
from typing import Union, Generator
from unittest.mock import MagicMock, create_autospec

from abcnet.netstats import NetworkMessagesStats, LogEvent, StatsReaders


class NetStatsTest(unittest.TestCase):

    def test_netstats_obj(self):
        stats = NetworkMessagesStats()
        self.assertFalse(stats.has_event(0))
        e1: Union[LogEvent, MagicMock] = MagicMock()
        stats.push_event(e1)
        self.assertTrue(stats.has_event(0))
        self.assertFalse(stats.has_event(1))
        self.assertIs(stats.get_event(0), e1)
        self.assertRaises(IndexError, stats.get_event, 1)
        stats.del_event(10)
        self.assertRaises(IndexError, stats.get_event, 0)
        self.assertEqual(stats.events, [])

    def test_stats_reader(self):
        import abcnet.settings as settings
        settings.NetStatSettings.EVENT_DELETE_BATCH_SIZE = 4

        stats: NetworkMessagesStats = NetworkMessagesStats()
        stats_reader = StatsReaders(stats)
        stats_reader.register_reader("a")
        stats_reader.register_reader("b")

        self.assertRaises(StopIteration, next, stats_reader.read("a"))
        self.assertRaises(StopIteration, next, stats_reader.read("b"))

        stats.push_event(1)
        stats.push_event(2)

        a_gen = stats_reader.read("a")
        assert next(a_gen) == 1
        assert next(a_gen) == 2
        self.assertRaises(StopIteration, next, a_gen)

        stats.push_event(3)
        stats.push_event(4)

        b_gen = stats_reader.read("b")
        assert next(b_gen) == 1
        assert next(b_gen) == 2
        assert next(b_gen) == 3
        assert next(b_gen) == 4
        self.assertRaises(StopIteration, next, b_gen)

        list = [i for i in stats_reader.read("b")]
        assert list == []

        stats_reader.register_reader("c")
        c_gen = stats_reader.read("c")
        list = [i for i in c_gen]
        assert list == [1,2,3,4]

        assert stats_reader.reader_positions == {
            "a" : 2,
            "b" : 4,
            "c" : 4,
        }

        stats.push_event(5)

        list = [i for i in stats_reader.read("a")]
        assert list == [3, 4, 5]

        stats.push_event(6)

        assert stats_reader.reader_positions == {
            "a" : 1,
            "b" : 0,
            "c" : 0,
        }
        assert stats.events == [5, 6]

        assert [6] == [i for i in stats_reader.read("a")]
        assert [5, 6] == [i for i in stats_reader.read("b")]
        assert [5, 6] == [i for i in stats_reader.read("c")]





