import sqlite3

import abccore.prefix_tree as prefix_tree
from abccore.DAG import *
from abccore.agent_crypto import parse_to_bytes, parse_from_bytes
from abcnet.structures import ItemType


def __init(filename):
    """The init function will try to connect to a database given by :param filename. If there is no such file, the init
    will create that file with the tables 'abc_data', 'ack', 'txn' and 'wallet'.
    The function will :return False, if the connected database is empty, such that the load_data() function can then
    fall back to the genesis.db file.
    """
    # Create database if possible
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    non_empty = False
    if not filename == "genesis.db":
        try:
            cursor.execute("""CREATE TABLE abc_data (
                keyset varbinary,
                balance varbinary,
                last_ack text,
                stake text,
                transaction_history text,
                ack_length text
                )
            """)
        except:
            # print("There is already a table for agent fields")
            non_empty = True

    try:
        cursor.execute("""CREATE TABLE ack (
            ack_id varbinary,
            txn_id varbinary,
            prev_ack varbinary,
            signature varbinary
            )
        """)
    except:
        # print("There is already a table for ack")
        non_empty = True

    try:
        cursor.execute("""CREATE TABLE txn (
            txn_id varbinary,
            inputs varbinary,
            outputs varbinary,
            parents varbinary,
            val text,
            validator varbinary,
            signatures varbinary
            )
        """)
    except:
        # print("There is already a table for txn")
        non_empty = True

    try:
        cursor.execute("""CREATE TABLE wallet (
            id text,
            origin varbinary,
            own_key varbinary,
            state text,
            val text
            )
        """)
    except:
        # print("There is already a table for wallet")
        non_empty = True

    try:
        cursor.execute("""CREATE TABLE unconfirmed_nodes (
            state text,
            ack_id varbinary,
            txn_id varbinary,
            prev_ack varbinary,
            signatures varbinary,
            inputs varbinary,
            outputs varbinary,
            val text,
            validator varbinary
            )
        """)
    except:
        # print("There is already a table for unconfirmed nodes")
        non_empty = True

    try:
        cursor.execute("""CREATE TABLE unconfirmed_wallets (
            id text,
            origin varbinary,
            own_key varbinary,
            state text,
            val text
            )
        """)
    except:
        # print("There is already a table for unconfirmed wallets")
        non_empty = True

    conn.commit()
    conn.close()

    return non_empty


# functions
def __encode_unconfirmed(pending_transactions: dict, orphaned_nodes: dict, filename):
    # pending_transactions = {txn.identifier: [txn, Decimal(0)]}
    # orphaned_nodes = {txn.identifier: List[Node]}
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    __delete_table_data(cursor, "unconfirmed_wallets")
    __delete_table_data(cursor, "unconfirmed_nodes")

    pending_trans = pending_transactions.keys()
    for key in pending_trans:
        data = pending_transactions.get(key)
        node = data[0]
        value = data[1]
        __parse_unconfirmed_txn(cursor, "pending", node, value)

    orphans = orphaned_nodes.keys()
    for key in orphans:
        orphan_list = orphaned_nodes.get(key)
        for orphan in orphan_list:
            if isinstance(orphan, Transaction):
                __parse_unconfirmed_txn(cursor, key, orphan, "0")
            elif isinstance(orphan, Acknowledge):
                __parse_unconfirmed_ack(cursor, key, orphan, "0")

    conn.commit()
    conn.close()


def update_unconfirmed(pending_transactions: dict, filename="abc_save.db"):
    """This function adds a pending_transactions to the existing table"""
    __init(filename)
    # pending_transactions = {txn.identifier: [TXN, Decimal]}
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    pending_trans = pending_transactions.keys()
    for key in pending_trans:
        data = pending_transactions.get(key)
        node = data[0]
        value = data[1]
        __parse_unconfirmed_txn(cursor, "pending", node, value)

    conn.commit()
    conn.close()


def __parse_unconfirmed_txn(cursor, state, node, value):

    ack_id = b""
    prev_ack = b""
    txn_id = node.get_identifier()
    validator = node.get_validator()

    inputs = b""
    for wallet in node.get_inputs():
        __commit_agent_wallet(cursor, wallet, table="unconfirmed_wallets")
        inputs = inputs + bytes(wallet)

    outputs = b""
    for wallet in node.get_outputs():
        __commit_agent_wallet(cursor, wallet, table="unconfirmed_wallets")
        outputs = outputs + bytes(wallet)

    parents = b""
    if len(node.get_parents()) > 0:
        node_parents = node.get_parents().keys()

        for key in node_parents:
            parents += key

    signatures = b""
    sigs = node.get_signatures()
    for sig in sigs:
        signatures = signatures + sig[0] + sig[1]

    commit_args = [state, ack_id, txn_id, prev_ack, signatures, inputs, outputs, value, validator]

    __commit_unconfirmed_node(cursor, commit_args)


def __parse_unconfirmed_ack(cursor, state, node, value):
    sig = node.get_signature()

    ack_id = node.get_identifier()
    txn_id = node.get_trans_id()
    prev_ack = node.get_prev_ack()
    signatures = sig[1]
    inputs = b""
    outputs = b""
    validator = sig[0]

    commit_args = [state, ack_id, txn_id, prev_ack, signatures, inputs, outputs, value, validator]

    __commit_unconfirmed_node(cursor, commit_args)


def __commit_unconfirmed_node(cursor, args):

    sql = """INSERT INTO unconfirmed_nodes VALUES (
            :state,
            :ack_id,
            :txn_id,
            :prev_ack,
            :signatures,
            :inputs,
            :outputs,
            :val,
            :validator
            )"""

    cursor.execute(sql,
                   {
                       'state': args[0],
                       'ack_id': args[1],
                       'txn_id': args[2],
                       'prev_ack': args[3],
                       'signatures': args[4],
                       'inputs': args[5],
                       'outputs': args[6],
                       'val': str(args[7]),
                       'validator': args[8]
                   })


def __decode_unconfirmed(filename):
    pending_transactions = dict()
    orphaned_nodes = dict()

    wallets = {}
    wallet_data = __load_wallets(filename)
    for line in wallet_data:
        # for all wallets in table wallet of database filename
        # fill dict wallets with: wallets[id||origin] = [ own_key, state, value ]
        wallets[int(line[0]).to_bytes(2, "big").hex() + line[1]] = [line[2], line[3], line[4]]

    wallets_unc = {}
    wallet_data = __load_wallets(filename, table="unconfirmed_wallets")
    for line in wallet_data:
        # for all wallets in table wallet of database filename
        # fill dict wallets with: wallets[id||origin] = [ own_key, state, value ]
        wallets_unc[int(line[0]).to_bytes(2, "big").hex() + line[1]] = [line[2], line[3], line[4]]

    nodes = __load_data("unconfirmed_nodes", False, filename)
    # [ [0: state, 1: ack_id, 2: txn_id, 3: prev_ack, 4: signatures,
    # 5: inputs, 6: outputs, 7: value, 8: validator], ... ]

    if nodes is None:
        nodes = list()

    for line in nodes:
        signatures = []
        sig_data = line[4]
        while len(sig_data) > 0:
            # while string sig_data is not empty, restore signatures and add them to signatures list for this txn

            # sig_data is string of concatinated signature representations of the transaction signatures
            # e.g. sig_data = pk1||sig1||pk2...
            signatures.append((sig_data[0:32], sig_data[32:96]))
            sig_data = sig_data[96:]

        if not line[8] == b"":  # TXN
            inputs = []
            txn_data = line[5]
            while len(txn_data) > 0:
                # while string txn_data is not empty, restore wallets and add them to inputs list for this txn

                # txn_data is string of concatinated wallet representations of the transaction inputs
                # e.g. txn_data = wallet1.own_key||wallet1.origin||wallet1.id||wallet2.own_key||...
                wallet_key = txn_data[64:66].hex() + txn_data[32:64].hex()
                load_wallet = wallets_unc.get(wallet_key)
                if load_wallet is None:
                    load_wallet = wallets.get(wallet_key)

                restored_wallet = Wallet(txn_data[0:32],
                                         Decimal(load_wallet[2]),
                                         txn_data[32:64],
                                         int.from_bytes(txn_data[64:66], "big"))

                if load_wallet[1] == "0":
                    state = State.UNSPENT
                elif load_wallet[1] == "1":
                    state = State.PENDING
                else:
                    state = State.SPENT

                restored_wallet.set_state(state)
                inputs.append(restored_wallet)

                txn_data = txn_data[66:]

            outputs = []
            txn_data = line[6]
            while len(txn_data) > 0:
                # essentially the same loop as above, but for the transaction outputs

                key = txn_data[64:66].hex() + txn_data[32:64].hex()
                load_wallet = wallets_unc.get(key)
                if load_wallet is None:
                    load_wallet = wallets.get(key)

                restored_wallet = Wallet(txn_data[0:32],
                                         Decimal(load_wallet[2]),
                                         txn_data[32:64],
                                         int.from_bytes(txn_data[64:66], "big"))
                if load_wallet[1] == "0":
                    state = State.UNSPENT
                elif load_wallet[1] == "1":
                    state = State.PENDING
                else:
                    state = State.SPENT

                restored_wallet.set_state(state)
                outputs.append(restored_wallet)

                txn_data = txn_data[66:]

            val_key = line[8]

            node = Transaction(inputs, outputs, val_key)

            node.identifier = line[2]

        else:  # ACK
            val_key = signatures[0][0]  # An ACK has only one signature, of which the first entry is the val_key
            node = Acknowledge(line[2], line[3], val_key)
            node.identifier = line[1]

        node.signatures = signatures
        key = line[0]
        if not key == "pending":
            orphan_set = orphaned_nodes.get(key)
            if orphan_set is None:
                orphaned_nodes[key] = {node}
            else:
                orphan_set.add(node)
                orphaned_nodes.update({key: orphan_set})
        else:
            pending_transactions[line[2]] = [node, Decimal(line[7])]

    return [pending_transactions, orphaned_nodes]


def __encode_tree(tree: prefix_tree.Tree, filename):
    """Encode the prefix tree :param tree to be saved in the database :param filename.
    For each Node in the DAG, the function will call the parser __commit_agent_ack() or add_txn() depending on if the
    Node is an Acknowledge, or a Transaction.
    """

    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    nodes = tree.get_all()
    for node in nodes:
        if isinstance(node, Checkpoint):
            print("The Checkpoint won't be saved in ", filename)
        elif isinstance(node, Acknowledge):
            add_ack(cursor, node, filename)
        else:
            add_txn(cursor, node, filename)

    conn.commit()
    conn.close()


def __decode_tree(filename) -> 'Tree':
    """The function will retrieve all TXNs, ACKs and Wallets from the database :param filename and create a prefix_tree
    object from it.
    First, all wallet representations will be added to the dict wallets with
    key = bytes(id)||origin and value = [ own_key, state, value ]
    """
    tree = prefix_tree.Tree()
    unspent_outputs = set()
    node_request_set = set()

    wallets = {}
    for line in __load_wallets(filename):
        # for all wallets in table wallet of database filename
        # fill dict wallets with: wallets[id||origin] = [ own_key, state, value ]
        wallets[int(line[0]).to_bytes(2, "big").hex() + line[1]] = [line[2], line[3], line[4]]

    transactions = __load_data("txn", False, filename)
    transactions: list  # [ [txn_id, inputs, outputs, parents, val, validator, signatures], ... ]

    for txn in transactions:
        try:
            inputs = []
            parents = {}
            txn_data = txn[1]
            while len(txn_data) > 0:
                # while string txn_data is not empty, restore wallets and add them to inputs list for this txn

                # txn_data is string of concatinated wallet representations of the transaction inputs
                # e.g. txn_data = wallet1.own_key||wallet1.origin||wallet1.id||wallet2.own_key||...
                load_wallet = wallets.get(txn_data[64:66].hex() + txn_data[32:64].hex())
                restored_wallet = Wallet(txn_data[0:32],
                                         Decimal(load_wallet[2]),
                                         txn_data[32:64],
                                         int.from_bytes(txn_data[64:66], "big"))
                # add wallet.origin to transaction.parents
                parents[txn_data[32:64]] = txn_data[32:64]
                if load_wallet[1] == "0":
                    state = State.UNSPENT
                elif load_wallet[1] == "1":
                    state = State.PENDING
                else:
                    state = State.SPENT

                restored_wallet.set_state(state)
                inputs.append(restored_wallet)

                txn_data = txn_data[66:]

            outputs = []
            txn_data = txn[2]
            while len(txn_data) > 0:
                # essentially the same loop as above, but for the transaction outputs

                key = txn_data[64:66].hex() + txn_data[32:64].hex()
                load_wallet = wallets.get(key)
                restored_wallet = Wallet(txn_data[0:32],
                                         Decimal(load_wallet[2]),
                                         txn_data[32:64],
                                         int.from_bytes(txn_data[64:66], "big"))
                if load_wallet[1] == "0":
                    state = State.UNSPENT
                    unspent_outputs.add((restored_wallet.get_origin(), restored_wallet.get_id()))
                elif load_wallet[1] == "1":
                    state = State.PENDING
                else:
                    state = State.SPENT

                restored_wallet.set_state(state)
                outputs.append(restored_wallet)

                txn_data = txn_data[66:]

            val_key = txn[5]

            if len(inputs) == 0:
                trans = Genesis(outputs)
            else:
                trans = Transaction(inputs, outputs, val_key)

            trans.identifier = txn[0]
            trans.parents = parents

            signatures = []
            sig_data = txn[6]
            while len(sig_data) > 0:
                # while string sig_data is not empty, restore signatures and add them to signatures list for this txn

                # sig_data is string of concatinated signature representations of the transaction signatures
                # e.g. sig_data = pk1||sig1||pk2...
                signatures.append((sig_data[0:32], sig_data[32:96]))
                sig_data = sig_data[96:]
            trans.signatures = signatures

            tree.add(trans.get_identifier(), trans)
        except TypeError:
            print("Corrupted data prevented the correct load of this TXN: ", txn_data[32:64].hex())
            item = (ItemType.TXN, txn_data[32:64].hex())
            node_request_set.add(item)

    acknowledges = __load_data("ack", False, filename)
    acknowledges: list  # [ [ack_id, txn_id, prev_ack, signature], ... ]

    for ack in acknowledges:
        try:
            signatures = []
            sig_data = ack[3]
            while len(sig_data) > 0:
                # the same loop as for txn
                signatures.append((sig_data[0:32], sig_data[32:96]))
                sig_data = sig_data[96:]

            val_key = signatures[0][0]  # An Ack should only have one signature and val_key is also stored in the signature

            restorend_ack = Acknowledge(ack[1], ack[2], val_key)

            restorend_ack.identifier = ack[0]
            restorend_ack.signatures = signatures

            tree.add(restorend_ack.get_identifier(), restorend_ack)
        except TypeError:
            print("Corrupted data prevented the correct load of this ACK: ", ack[0].hex())
            item = (ItemType.ACK, ack[0].hex())
            node_request_set.add(item)

    return [tree, unspent_outputs, node_request_set]


def write_data(args, password, tree: prefix_tree.Tree, filename):
    """This function will be called in the agent class. It parses the :param args to bytestrings and encrypts the
    key_set with :param password to let the parsed data be saved in the database :param filename.
    :param filename: name of the database file
    :param tree: agent_data.tree
    :param args: List of attributes of the agent:
        self.keyset,
        self.balance,
        self.last_acks,
        self.stake,
        self.transaction_history,
        self.ack_length,
        pending_transactions,
        orphaned_nodes
    :param password: password in bytes to encrypt the key pairs of the key_set included in args.
    """
    keyset_bytes = b""
    for key in args[0]:
        keyset_bytes = keyset_bytes + parse_to_bytes(key, password)

    args[0] = keyset_bytes

    balance = b""  # balance
    if len(args[1]) > 0:
        for wallet in args[1]:
            balance = balance + bytes(wallet)

    args[1] = balance

    last_acks = b""
    if args[2]:
        args[2]: dict
        acks = args[2].items()

        for pair in acks:
            last_acks += pair[0] + pair[1]
    args[2] = last_acks

    if len(args[3]) > 0:  # stake
        stake = b""
        for trans_id in args[3]:
            stake = stake + trans_id

        args[3] = stake
    else:
        args[3] = b""

    if len(args[4]) > 0:  # transaction_history
        transaction_history = args[4]
        transactions = b""
        for trans in transaction_history:
            transactions += trans

        args[4] = transactions
    else:
        args[4] = b""

    if not args[5]:
        args[5] = dict()

    ack_length = b""
    for pair in args[5].items():
        ack_length += pair[0] + int.to_bytes(pair[1], 32, "big")
    args[5] = ack_length

    __init(filename)
    if not filename == "genesis.db":
        __commit_agent_fields(args, filename)

    __encode_tree(tree, filename)
    __encode_unconfirmed(args[6], args[7], filename)


def update(args, filename):
    """Update last_ack and ack_length after each new acknowledge by the agent"""
    __init(filename)
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    sql = """UPDATE abc_data SET 
        last_ack = '""" + args[1].hex() + """', 
        ack_length = '""" + args[2] + """' 
        WHERE last_ack = '""" + args[0].hex() + """';"""

    cursor.execute(sql)
    conn.commit()

    conn.close()
    print("update done")


def __commit_agent_fields(args, filename):
    """Adds the parsed data in :param args and adds them to the table abc_data of the database :param filename."""

    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    sql = """INSERT INTO abc_data VALUES (
        :keyset,
        :balance,
        :last_ack,
        :stake,
        :transaction_history,
        :ack_length
        )"""

    cursor.execute(sql,
                   {
                       'keyset': args[0],
                       'balance': args[1],
                       'last_ack': args[2].hex(),
                       'stake': args[3],
                       'transaction_history': args[4],
                       'ack_length': args[5].hex()
                   })

    conn.commit()
    conn.close()
    # print("commit done")


def __commit_agent_txn(cursor, args):
    """This function adds a single transaction given in :param args to the table txn of database :param filename."""
    while len(args) < 7:  # sanity check after changes
        args.append(b'')
        print("This is an older version!")

    sql = """INSERT INTO txn VALUES (
        :txn_id,
        :inputs,
        :outputs,
        :parents,
        :val,
        :validator,
        :signatures
        )"""

    cursor.execute(sql,
                   {
                    'txn_id': args[0],
                    'inputs': args[1],
                    'outputs': args[2],
                    'parents': args[3],
                    'val': args[4],
                    'validator': args[5],
                    'signatures': args[6]
                   })


def __commit_agent_ack(cursor, args):
    """This function adds the parsed data in :param args to the table ack of the database :param filename."""
    while len(args) < 4:  # sanity check after changes
        args.append(b'')
        print("This is an older version!")

    sql = """INSERT INTO ack VALUES (
        :ack_id,
        :txn_id,
        :prev_ack,
        :signature
        )"""

    cursor.execute(sql,
                   {
                       'ack_id': args[0],
                       'txn_id': args[1],
                       'prev_ack': args[2],
                       'signature': args[3]
                   })


def __delete_table_data(cursor, table):
    sql = "DELETE FROM " + table + ";"
    cursor.execute(sql)


def __commit_agent_wallet(cursor, wallet, table="wallet"):
    sql = """INSERT INTO """ + table + """ VALUES (
        :id,
        :origin,
        :own_key,
        :state,
        :val
        )"""

    cursor.execute(sql,
                   {
                       'id': str(wallet.get_id()),
                       'origin': wallet.get_origin().hex(),
                       'own_key': wallet.get_pk(),
                       'state': str(wallet.get_state().value),
                       'val': str(wallet.get_value())
                   })


def load_data(password, filename):
    """This function will be called by the AgentData to load all data of the previous session, or to load the genesis
    file as a backup.
    """
    if not __init(filename):
        # if load of database filename was unsuccessful
        if not filename == "genesis.db":
            # try the backup
            filename = "genesis.db"
            if not __init(filename):
                raise ImportError
        else:
            # alert the user if the genesis.db was not found
            raise FileNotFoundError

    output = [[]]
    try:
        tree_data = __decode_tree(filename)
    except LookupError:
        tree_data = __decode_tree("genesis.db")

    tree = tree_data[0]
    tree: prefix_tree.Tree

    if not filename == "genesis.db":
        args = __load_data("abc_data", True, filename)  # True -> only load last save of user data
        # args = [ keyset, balance, last_ack, stake, transaction_history, ack_length ]

        if not args:
            raise LookupError

        if len(args[0]) > 0:
            keyset = set()
            keyset_bytes = args[0]
            while len(keyset_bytes) > 0:
                # check if this key is already in the keyset
                if keyset_bytes[0:32] not in keyset:
                    # reconstruct key_set out of the bytestring
                    output[0].append(parse_from_bytes(keyset_bytes[0:32], password))

                    # add key to sanity set and delete it from keyset_bytes
                    keyset.add(keyset_bytes[0:32])

                keyset_bytes = keyset_bytes[32:]

        output.append([])  # balance
        if len(args[1]) > 0:

            balance = args[1]
            while len(balance) > 0:
                # balance contains concatenated representations of wallets which the user owns
                # as long as balance is not empty, search in the previously restored tree for the current wallet
                try:
                    trans = tree.search(balance[32:64]).get_node()
                    restored_wallet = trans.get_outputs()[int.from_bytes(balance[64:66], "big")]
                    if restored_wallet.get_pk() == balance[0:32]:
                        output[1].append(restored_wallet)
                except AttributeError:
                    print("Failed to match a wallet with the DAG.")

                balance = balance[66:]

        last_acks = dict()
        # the default of last_ack is the genesis or latest checkpoint
        if args[2] is not None:
            # if the user has made an Ack before, his latest_ack is set to that Ack

            saved_last_acks = bytes.fromhex(args[2])
            while len(saved_last_acks) > 0:
                last_acks[saved_last_acks[0:32]] = saved_last_acks[32:64]
                saved_last_acks = saved_last_acks[64:]
        else:
            last_acks = None
        output.append(last_acks)

        output.append([])  # stake
        if len(args[3]) > 0:
            # stake is a list of transactions, represented by their identifiers, in which the user gained stake
            stake = args[3]
            while len(stake) > 0:
                output[3].append(stake[0:32])
                stake = stake[32:]

        output.append([])  # transaction_history
        if len(args[4]) > 0:
            # this is a concatenation of Transaction identifiers of those, which the user made himself
            transaction_history = args[4]
            while len(transaction_history) > 0:
                output[4].append(transaction_history[0:32])
                transaction_history = transaction_history[32:]

        ack_length = dict()
        # the default of last_ack is the genesis or latest checkpoint
        if args[5] is not None:
            # if the user has made an Ack before, his latest_ack is set to that Ack

            saved_ack_length = bytes.fromhex(args[5])
            while len(saved_ack_length) > 0:
                ack_length[saved_ack_length[0:32]] = int.from_bytes(saved_ack_length[32:64], "big")
                saved_ack_length = saved_ack_length[64:]
        else:
            ack_length = None
        output.append(ack_length)

    # sanity check for the case where filename == genesis.db
    while len(output) < 5:
        output.append([])
    if len(output) == 5:
        output.append(dict())

    output.extend(tree_data)
    if not filename == "genesis.db":
        output.extend(__decode_unconfirmed(filename))
    else:
        output.extend([None, None])

    return output


def __load_data(table, only_last_item, filename):
    """Load data of a specific :param table from the database :param filename. The :param only_last_item denotes if the
    output should be only the last row (only_last_item == False), or all rows in the table (only_last_item == True).
    If the data retrieved from the table is empty, then the function will fall back to the genesis.db to retrieve the
    initial data.
    """
    # Connect to database
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM " + table)
    args = cursor.fetchall()

    # Commit changes
    conn.commit()
    # Close connection
    conn.close()
    # print("load done")

    if len(args) == 0 and not table == "ack":
        if not filename == "genesis.db":
            return list()
        else:
            raise ImportError
    elif only_last_item:  # distinguish between only the last row or the whole table
        # [txn_id, inputs, outputs, parents, val, validator, signatures]
        return args[-1]  # last row of data, to be used for loading genesis
    else:
        # [ [txn_id, inputs, outputs, parents, val, validator, signatures], ... ]
        return args  # all rows of data, to be used for loading transactions


def __load_wallets(filename, table="wallet"):
    # Connect to database
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    command = "SELECT * FROM " + table
    # print(command)
    cursor.execute(command)
    args = cursor.fetchall()

    conn.commit()
    conn.close()
    # print("load done")

    return args


def add_txn(cursor, node: Transaction, filename):
    """This function parses the fields of the Transaction :param node to then call the function __commit_agent_txn()
    to add the parsed data to the table txn of database :param filename.
    It parses the fields of node as follows:
    node.identifier -> bytes
    node.inputs -> bytes, concatenated representations, each of length 66
    node.outputs -> bytes, concatenated representations, each of length 66
    node.parents -> bytes, concatenated PKs in form of bytes, each of length 32
    node.value -> string
    node.validator -> bytes
    node.signatures -> bytes, concatenated representations in form of bytes, each of length 96
    """
    if isinstance(node, Checkpoint):
        raise AttributeError("Checkpoints will not be saved in this DB!")
    commit_args = [node.get_identifier()]

    internal_call = True
    if cursor is None:
        internal_call = False
        __init(filename)
        conn = sqlite3.connect(filename)
        cursor = conn.cursor()

    inputs = b""
    if not isinstance(node, Genesis):
        for wallet in node.get_inputs():
            __commit_agent_wallet(cursor, wallet)
            inputs = inputs + bytes(wallet)
    commit_args.append(inputs)

    outputs = b""
    for wallet in node.get_outputs():
        __commit_agent_wallet(cursor, wallet)
        outputs = outputs + bytes(wallet)
    commit_args.append(outputs)

    parents = b""
    if len(node.get_parents()) > 0:
        node_parents = node.get_parents().keys()

        for key in node_parents:
            parents += key
    commit_args.append(parents)

    commit_args.append(str(node.get_value()))
    if not isinstance(node, Genesis):
        commit_args.append(node.get_validator())
    else:
        commit_args.append(None)

    signatures = b""
    if not isinstance(node, Genesis):
        sigs = node.get_signatures()
        for sig in sigs:
            signatures = signatures + sig[0] + sig[1]
    commit_args.append(signatures)

    __commit_agent_txn(cursor, commit_args)

    if not internal_call:
        conn.commit()
        conn.close()


def add_ack(cursor, node: Acknowledge, filename):
    """Parses the fields of the Acknowledge :param node to call then __commit_agent_ack() to add the parsed data to the
    table txn of database :param filename.
    node.identifier, node.trans_id and node.prev_ack are already bytes,
    node.signatures will be parsed to bytes of length 96
    """
    internal_call = True
    if cursor is None:
        internal_call = False
        __init(filename)
        conn = sqlite3.connect(filename)
        cursor = conn.cursor()

    args = [node.get_identifier(), node.get_trans_id(), node.get_prev_ack()]
    sig = node.get_signature()
    args.append(b'' + sig[0] + sig[1])

    __commit_agent_ack(cursor, args)

    if not internal_call:
        conn.commit()
        conn.close()


def delete_old_data(filename):
    __init(filename)
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM ack")
    cursor.execute("DELETE FROM txn")
    cursor.execute("DELETE FROM wallet")
    cursor.execute("DELETE FROM unconfirmed_nodes")
    cursor.execute("DELETE FROM unconfirmed_wallets")

    conn.commit()
    conn.close()


def update_wallet(wallet, filename):  # deprecated? only used in method which may be deprecated by itself
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    sql = """UPDATE wallet SET 
        state = '""" + str(wallet.get_state().value) + """'
        WHERE id = '""" + str(wallet.get_id()) + """' AND 
        origin = '""" + wallet.get_origin().hex() + """';"""

    cursor.execute(sql)
    conn.close()
