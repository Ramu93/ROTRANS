import sqlite3
import logging
from typing import List, Union
from abccore.DAG import Wallet
from decimal import Decimal
from abccore.DAG import Checkpoint
import os.path

filename = 'checkpoint.db'


def ckpt_save(ckpt: Checkpoint) -> bool:
    """
    This function saves the checkpoint data into the database.
    Parameters:
            ckpt (Checkpoint): object of type checkpoint

        Returns:
            bool: status of the save operation
    """
    # data preparation for database query
    args = [str(ckpt.id.hex()), str(ckpt.origin.hex()), ckpt.lock_time.__str__(), str(ckpt.ack_length),
            str(ckpt.total_stake)]

    # stake dictionary saved as string
    stake_string = ''
    for key in ckpt.stake_dict:
        stake_string += key.hex() + ':' + str(ckpt.stake_dict[key]) + ';'
    args.append(stake_string)

    # unspent outputs saved as string
    utxos = ''
    for utxo in ckpt.utxos:
        utxos += utxo.own_key.hex() + ":" + str(utxo.value) + ":" + utxo.origin.hex() + ":" + str(utxo.id) + ";"

    args.append(utxos)
    args.append(str(ckpt.nutxo))

    # fee rewards saved as string
    fee_rewards_str = ''
    for wallet in ckpt.outputs:
        fee_rewards_str += wallet.own_key.hex() + ":" + str(wallet.value) + ":" + wallet.origin.hex() + ":" \
                           + str(wallet.id) + ";"
    args.append(str(fee_rewards_str))
    args.append(str(ckpt.total_coins))
    args.append(str(ckpt.height))
    args.append(str(ckpt.miner.hex()))
    # Initialize the database if the db file does not exist
    if not os.path.isfile(filename):
        ckpt_init()
    connection = sqlite3.connect(filename)
    cursor = connection.cursor()

    # save method call on data prepared
    ckpt_encode(args, cursor)
    connection.commit()
    connection.close()
    logging.info("Genesis Saved")
    return True


def string_to_wallets(walletstring: str) -> List[Wallet]:
    """
    Changes wallet list string from db to wallet list. This function is used to create checkpoint object from db file.
    Parameters:
        walletstring (str): wallet list string extracted form checkpoint db.

    Returns:
        wallet_list (List[Wallet]): list of wallets
    """
    wallets = walletstring.strip().split(';')
    wallet_list = []
    for wallet in wallets:

        if wallet == '':
            break
        sp = wallet.strip().split(':')
        if str(sp[3]) == 'None':
            walletid = 0
        else:
            walletid = int(str(sp[3]))
        wallet_list.append(Wallet(bytes.fromhex(str(sp[0])), Decimal(str(sp[1]).strip()),
                                  bytes.fromhex(str(sp[2])), walletid))
    return wallet_list


def ckpt_extract(checkpoint_height: Union[None, int, bytes] = None) -> Checkpoint:
    """
    Extracts the checkpoint data saved in the database according to given input.
        if checkpoint_height is int: returns checkpoint with the given height
        if checkpoint_height is bytes: returns checkpoint which matches the given identifier
        if checkpoint_height is None: returns checkpoint which has maximum height in the database

    Parameters:
        checkpoint_height(Union[None, int, bytes]): checkpoint height, it can be unique identifier of checkpoint,
            height as an integer or default none.

    Returns:
        Checkpoint: checkpoint object generated from saved object
    """
    connection = sqlite3.connect(filename)
    cursor = connection.cursor()
    if checkpoint_height is None:
        query = """SELECT * FROM checkpoint WHERE height=(select max(height) from checkpoint)"""
    elif isinstance(checkpoint_height, bytes):
        query = """SELECT * FROM checkpoint WHERE id=""" + str(checkpoint_height.hex()) + """;"""
    elif isinstance(checkpoint_height, int):
        query = """SELECT * FROM checkpoint WHERE height=""" + str(checkpoint_height) + """;"""
    cursor.execute(query)
    args = cursor.fetchall()
    connection.commit()
    connection.close()
    wallet_list = string_to_wallets(args[0][6])

    fee_rewards = string_to_wallets(args[0][8])

    stake_list = {}
    stake_list_string = args[0][5].strip().split(';')
    for stake in stake_list_string:
        if stake == '':
            break

        validator = bytes.fromhex(stake.split(':')[0])

        validator_stake = Decimal(str(stake.split(':')[1]))
        stake_list[validator] = validator_stake

    origin = bytes.fromhex(str(args[0][1]))
    miner = bytes.fromhex(str(args[0][11]))

    # object creation
    checkpoint = Checkpoint(origin, int(args[0][10]), float(args[0][2]), int(args[0][3]), wallet_list,
                            fee_rewards, stake_list, int(args[0][7]), Decimal(args[0][4]), Decimal(args[0][9]), miner)

    return checkpoint


def ckpt_encode(args, cursor):
    """
    Saves the provided arguments in the checkpoint db.

    Parameters:
        args (list): list of checkpoint object attributes as list.
        cursor (Cursor): cursor of db connection.
    """
    query = """INSERT INTO checkpoint VALUES (
        :id,
        :head,
        :lock_time,
        :tree_length,
        :total_stake,
        :stake_dict,
        :outputs,
        :nutxo,
        :fee_rewards,
        :total_coins,
        :height,
        :miner)"""

    cursor.execute(query, {'id': args[0],
                           'head': args[1],
                           'lock_time': args[2],
                           'tree_length': args[3],
                           'total_stake': args[4],
                           'stake_dict': args[5],
                           'outputs': args[6],
                           'nutxo': args[7],
                           'fee_rewards': args[8],
                           'total_coins': args[9],
                           'height': args[10],
                           'miner': args[11]
                           })


def ckpt_init():
    """
    This function initialize db file for checkpoint database.
    """
    connection = sqlite3.connect(filename)
    cursor = connection.cursor()
    try:
        cursor.execute("""CREATE TABLE IF NOT EXISTS checkpoint(
            id text type UNIQUE,
            head text,
            lock_time text,
            tree_length text,
            total_stake text,
            stake_dict text,
            outputs text,
            nutxo text,
            fee_rewards text,
            total_coins text,
            height text,
            miner text
            )
            """)
        connection.commit()
        connection.close()
    except Exception as e:
        print(e)
        logging.error('Table creation failed.')
        return
