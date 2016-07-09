import unittest
from meduzach.connections import Connector


class TestConnector(unittest.TestCase):
    def test_empty(self):
        c = Connector()
        c.emit('action', {'a': 123})

    def test_connect(self):
        c = Connector()
        abc = []
        bcd = []

        def handle_abc(sender, data):
            self.assertEqual(sender, c)
            abc.append(data)

        def handle_abc2(sender, data):
            self.assertEqual(sender, c)
            abc.append(data + "2")

        def handle_bcd(sender, data):
            self.assertEqual(sender, c)
            bcd.append(data)

        c.connect('abc', handle_abc)
        c.connect('abc', handle_abc2)
        c.connect('bcd', handle_bcd)

        c.emit('abc', 'abc_data')
        c.emit('bcd', 'bcd_data')
        c.emit('cde', 'cde_data')
        c.emit('abc', 'abc_data3')

        self.assertEqual(abc,
                         ['abc_data', 'abc_data2', 'abc_data3', 'abc_data32'])
        self.assertEqual(bcd, ['bcd_data'])

    def test_disconnect(self):
        c = Connector()
        abc = []

        def handle_abc(sender, data):
            self.assertEqual(sender, c)
            abc.append(data)

        def handle_abc2(sender, data):
            self.assertEqual(sender, c)
            abc.append(data + "2")

        conn_id = c.connect('abc', handle_abc)
        c.connect('abc', handle_abc2)

        c.emit('abc', 'abc_data')

        c.disconnect(conn_id)

        c.emit('abc', 'abc_data3')

        self.assertEqual(abc,
                         ['abc_data', 'abc_data2', 'abc_data32'],
                         c.connections)
