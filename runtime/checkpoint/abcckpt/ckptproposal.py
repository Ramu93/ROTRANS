import decimal
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from typing import Union, Dict, Tuple, List
from abccore.DAG import Acknowledge, Transaction, Wallet, Genesis, get_wallet_value, State, Checkpoint, Node
from abccore.checkpoint_service import CheckpointService
from abcckpt.ckpt_constants import ALPHA, FEE_THRESHOLD, REWARD
from abccore.prefix_tree import Tree
from abcckpt.pre_checkpoint import AgentService
import logging

logger = logging.getLogger(__name__)
CKPT_GENERATION_CONTEXT = decimal.Context(prec=16, rounding=decimal.ROUND_DOWN)


class Ckpt_Proposal:
    """
    This class manages the checkpoint creation from the DAG tree.
    """

    def __init__(self, dagtree: Tree, lastid: bytes, height, ack_len: int, miner: bytes,
                 ckpt_service: CheckpointService):

        self.lastckptid = lastid  # identifier of the last checkpoing
        self.dagtree = dagtree  # DAG tree of the Agent
        self.miner = miner  # public key of the checkpoint creator
        self.height = height  # height of the checkpoint
        self.locktime = datetime.utcnow().timestamp()  # checkpoint timestamp
        self.outputs: List[Wallet] = []  # list of wallets for storing unspent outputs
        self.fee_rewards: List[Wallet] = []  # list of wallets for storing fee rewards outputs
        self.stake_list = {}
        # Calculation of outputs, stake and fee reward
        outputs, delegated_stake, fee_reward = self.extract_utxo(self.dagtree, ckpt_service)

        old_context = decimal.getcontext()
        decimal.setcontext(CKPT_GENERATION_CONTEXT)
        try:
            self.__extract_lists(outputs, delegated_stake,
                                 fee_reward)  # initializes outputs, fee_rewards and stake_list
        finally:
            decimal.setcontext(old_context)
        self.nutxo = len(self.outputs)
        self.Ckpt = Checkpoint(self.lastckptid, height, self.locktime, ack_len,
                               self.outputs, self.fee_rewards, self.stake_list,
                               self.nutxo, self.total_stake(), self.total_coins(), miner)

    def extract_utxo(self, dag: Tree, ckpt_service):
        """
        Calculates unspent transaction outputs, fees, and stake from DAG.
        Parameters:
            dag (Tree): copy of DAG tree received from the agent.
            ckpt_service (CheckpointService): checkpointn service object
        Returns:
            outputs (List[Wallet]): list of utxo wallets
            delegated_stake_quantized (dict): delegated stake earned by each validator
            fee_reward_quantized (List[Wallet]): list of fee rewards for the validators
        """

        outputs: Dict[Tuple[bytes, int], Wallet] = dict()

        # This dictionary contains the outputs that we are spending ahead of time.
        # It maps from wallet to a flag called `output_spend_but_not_produced`
        # If the flag of wallet is True, then we have encountered a txn that spends the wallet
        # but have not yet found the txn that produces the wallet as its output.
        # Later on we find the output and then we set this flag to False.
        spent: Dict[Tuple[bytes, int], bool] = dict()

        delegated_stake: Dict[bytes, Decimal] = dict()

        fee_reward: Dict[bytes, Decimal] = dict()

        def get_stake_owner(node: Union[Transaction, Genesis], output_id: int) -> bytes:
            """Returns the public key of the owner of the stake mentioned in the transaction or Genesis.

            Parameters:
                node (TreeLeaf): node in the DAG tree structure(transaction/genesis).
                output_id (int): id of the wallet
            Returns:
                (bytes) owner of the stake extracted from transaction/genesis.
            """
            stake_owner: bytes
            if isinstance(node, Genesis):
                stake_owner = node.outputs[output_id].own_key
            elif isinstance(node, Transaction):
                if node.validator_key is not None:
                    stake_owner = node.validator_key
                else:
                    stake_owner = node.outputs[output_id].own_key
            else:
                raise ValueError("Unexpected node type: " + str(node))
            return stake_owner

        def change_stake(key: bytes, amount: Decimal) -> None:
            """
            Adds the stake for the given key by provided amount.

            Parameters:

                key (bytes): Public key of the validator
                amount(Decimal): Amount to be changed for the validator key
            """
            assert key is not None
            assert amount != 0
            if key not in delegated_stake:
                delegated_stake[key] = Decimal(0.0)
            delegated_stake[key] += amount

        def remove_stake(wallet: Wallet) -> None:
            """
            Subtracts the stake from the last owner.
            Parameters:
                wallet(Wallet): wallet to be removed from last stake owner
            """
            orig_txn_tl = dag.search(wallet.origin)
            if orig_txn_tl is None:
                raise ValueError(f"Couldn't find the original txn of the input wallet {wallet} "
                                 f"in order to remove the del stake.")
            assert isinstance(orig_txn_tl.get_node(), Transaction) or isinstance(orig_txn_tl.get_node(), Genesis)
            stake_owner: bytes = get_stake_owner(orig_txn_tl.get_node(), wallet.id)
            assert isinstance(stake_owner, bytes)
            change_stake(stake_owner, -wallet.value)

        def remove_output(wallet: Wallet) -> None:
            """
            Deletes the inputs of the transaction from recorded "output" list and if exists in "spent" list then
             set to "True".
             Parameters:
                 wallet (Wallet): wallet to be removed from output list.

            """
            if (wallet.origin, wallet.id) in outputs:
                del outputs[(wallet.origin, wallet.id)]
            else:
                spent[(wallet.origin, wallet.id)] = True
            if wallet.state != State.SPENT:
                raise Exception("Output is not in spent state although it is spent by another txn.")

        def add_output(wallet: Wallet) -> None:
            """Adds the outputs to output list and sets the spent wallet to False if present,
             if not present:->
                then Adds the outputs to output list.

                Parameters:
                    wallet (Wallet): wallet to add in the output list.
            """
            if (wallet.origin, wallet.id) in spent:
                if spent[(wallet.origin, wallet.id)]:
                    spent[(wallet.origin, wallet.id)] = False
                    return
                else:
                    raise Exception("Output wallet was already spent: " + str(wallet))
            outputs[(wallet.origin, wallet.id)] = wallet

        def relegate_owner(input_wallets: List[Wallet], output_wallets: List[Wallet]) -> None:
            """
            Keeps track of the latest state of input and output list.
            Parameters:
                input_wallets (List[Wallet]): list of wallets from input of node(transaction/checkpoint)
                output_wallets(List[Wallet]): list of wallets from output of node(transaction/genesis/checkpoint)
            """
            if input_wallets is not None:
                for w in input_wallets:
                    remove_output(w)
                for w in output_wallets:
                    add_output(w)

        def reward_fee(txn: Transaction, ack: Acknowledge) -> None:
            """
            Rewards the fee for acknowledgement found and changes the stake accordingly.
            Parameters:
                txn (Transaction): transaction found for the respective acknowledgement.
                ack (Acknowledge): acknowledgement object
            """
            validator = ack.pb_key
            fee = get_wallet_value(txn.inputs) - txn.get_value()
            assert fee > 0
            feepart = ALPHA * fee * (ckpt_service.delegated_stake(validator) / ckpt_service.stake_sum())
            if feepart < FEE_THRESHOLD:
                return
            if validator not in fee_reward:
                fee_reward[validator] = feepart
            else:
                fee_reward[validator] += feepart

            change_stake(validator, feepart)

        last_ckpt: Checkpoint = dag.get_latest_checkpoint()
        assert last_ckpt is not None
        utxo_wallet_set = set()
        if isinstance(last_ckpt, Checkpoint):
            utxo_wallet_set = set(map(lambda w: w.origin, last_ckpt.utxos))

        def is_in_old_dag(n: Node):
            if isinstance(n, Transaction):
                txn: Transaction = n
                if txn.get_identifier() in utxo_wallet_set:
                    return True
                else:
                    return False
                # if len(txn.get_parents()) == 1 and txn.get_parents()[0] == self.lastckptid:
                #     return True
                # else:
                #     for p in txn.get_parents():
                #         assert p != self.lastckptid
                #     return False
            elif isinstance(n, Acknowledge):
                ack: Acknowledge = n
                tl = dag.search(ack.get_trans_id())
                if tl is None or is_in_old_dag(tl.node):
                    return True
                else:
                    return False
            elif isinstance(n, Genesis):
                n: Genesis
                if n.get_identifier() != self.lastckptid:
                    return True  # This node is a very old checkpoint or genesis.
                else:
                    return False  # The last checkpoint is not counted as old
            else:
                raise ValueError(f"Unexpected node type: {n}, class: {n.__class__}")

        for node in dag.get_all():
            if is_in_old_dag(node):
                # We are not interested in old nodes
                continue
            if isinstance(node, Genesis):
                # The previous checkpoint
                if isinstance(node, Checkpoint):
                    # We use the prev utxo set as a basis of owner ship
                    relegate_owner([], node.utxos)
                    # We use the prev stake distribution as a basis
                    prev_stake = node.get_stake_list()
                    for stake_owner, stake_value in prev_stake.items():
                        change_stake(stake_owner, stake_value)  # Add stake values to each entry

                # A genesis generates money and fees. Add it as new spendable outputs and stake:
                for output in node.outputs:
                    change_stake(output.own_key, output.value)
                relegate_owner([], node.outputs)
            elif isinstance(node, Transaction):
                node: Transaction

                # Change the owner of the coins
                inputs: List[Wallet] = node.inputs
                outp: List[Wallet] = node.outputs

                # Change owner ship of money
                relegate_owner(inputs, outp)
                assert node.validator_key is not None
                value = get_wallet_value(node.outputs)
                change_stake(node.validator_key, value)
                assert len(inputs) > 0
                # Remove stake from the previous delegated stake.
                # Because the txn is not old, we should find it:
                for input in inputs:
                    remove_stake(input)

            # Award the fees
            elif isinstance(node, Acknowledge):
                node: Acknowledge
                txn_tl = dag.search(node.get_trans_id())
                if txn_tl is None or txn_tl.get_node() is None:
                    raise ValueError(f"Couldn't find in the DAG the txn {node.get_trans_id().hex()} of the ack {node}")
                txn = txn_tl.get_node()
                if not isinstance(txn, Transaction):
                    raise ValueError(f"Expected the ack {node} to acknowledge a txn. Instead it points to: {txn},"
                                     f" class: {txn.__class__}")
                reward_fee(txn, node)

        # Finalize the stake
        delegated_stake_filtered = dict()

        for owner, stake in delegated_stake.items():
            if stake < 0:
                raise Exception(f"Delegated stake of owner {owner} is negaitve: {stake}")
            if stake > 0:
                delegated_stake_filtered[owner] = stake

        for wallet, output_spent_but_not_produced in spent.items():
            if output_spent_but_not_produced:
                raise Exception(f"The wallet {wallet} was spent but we found to txn for it..")

        # Quantize the fees and stage sum:
        fee_reward_quantized = dict()
        for owner, value in fee_reward.items():
            val_q = value.quantize(Decimal(".00000000000001"), rounding=ROUND_HALF_EVEN)
            fee_reward_quantized[owner] = val_q

        # Quantize the stake
        delegated_stake_quantized = dict()
        for owner, value in delegated_stake_filtered.items():
            val_q = value.quantize(Decimal(".00000000000001"), rounding=ROUND_HALF_EVEN)
            delegated_stake_quantized[owner] = val_q

        return outputs, delegated_stake_quantized, fee_reward_quantized

    def __extract_lists(self, outputs: Dict[Tuple[bytes, int], Wallet], delegated_stake: Dict[bytes, Decimal],
                        fee_reward: Dict[bytes, Decimal]) -> None:
        """
        Transforms the output dictionary to list and adds the reward for checkpoint miner.
        Parameters:
            outputs (Dict[Tuple[bytes, int]): dictionary of wallets
            delegated_stake (Dict[bytes,Decimal]: dictionary of stake holders
            fee_reward (Dict[bytes,Decimal]): dictionary of the validators with earned rewards

        """
        self.outputs = list(outputs.values())
        self.stake_list = delegated_stake

        # stake for the reward
        if self.miner not in self.stake_list:
            self.stake_list[self.miner] = Decimal(0)
        self.stake_list[self.miner] += REWARD

        walletid = 0
        for owner, reward in fee_reward.items():
            w = Wallet(owner, reward, None, walletid)
            walletid += 1
            self.fee_rewards.append(w)
        # Fee reward for validator as wallet
        self.fee_rewards.append(Wallet(self.miner, REWARD, None, walletid))

    def get_stake_list(self) -> Dict:
        """
        Returns the stake list dictionary
        """
        return self.stake_list

    def get_stake(self, validator):
        """
        Returns stake of a validator
        Parameters:
            validator: validator id
        Returns: stake value of validator
        """
        return self.stake_list[validator]

    def total_stake(self) -> Decimal:
        """
        Calculates the total stake existing in the system.
        """

        stake_sum = Decimal(0)
        for i in self.stake_list:
            stake_sum += self.stake_list[i]
        return stake_sum.quantize(Decimal(".00000000000001"), rounding=ROUND_HALF_EVEN)

    def total_coins(self) -> Decimal:
        """
        calculates the total monetized coin in the system.
        Returns:
            Decimal: Total money in the system
        """
        coin_sum = Decimal(0)
        for i in self.outputs:
            coin_sum += i.value
        for fr in self.fee_rewards:
            coin_sum += fr.value
        return coin_sum.quantize(Decimal(".00000000000001"), rounding=ROUND_HALF_EVEN)


class PostCheckpoint:

    @staticmethod
    def checkpoint_verify(dagtree: Tree, checkpoint: Checkpoint, ckpt_service: CheckpointService,
                          agentservice: AgentService) -> Tuple[bool, str]:
        """
        Checks the validity of the checkpoint, if transaction is not found it adds the transaction id to pending lists
        which verify/request the network for missing transaction id.
        :param dagtree: refrence to the dagtree object.
        :param ckpt_service: checkpoint service
        :param checkpoint: checkpoint received from the network.
        :param agentservice: agenet service object
        :returns: True if checkpoint is valid, False if checkpoint data is invalid; status is returned as "PENDING" if
        there are txns that requires to be fetched.

        """
        pending: Dict[Tuple[bytes, int], Wallet] = dict()
        missing_txn: List[bytes] = list()

        def verify_output(output: Wallet) -> bool:
            """
            Verifies the existence of the given wallet. If not found in the DAG then adds to the pending list.
            """
            txn = dagtree.search(output.origin)
            if txn is None:
                pending[(output.origin, output.id)] = output
            else:
                found = False
                for out in txn.node.outputs:
                    if out.equals(output):
                        found = True
                        if (output.origin, output.id) in pending:
                            del pending[(output.origin, output.id)]
                        break
                if not found:
                    return False  # txn was found but output do not match
            return True

        # check height
        if checkpoint.height != ckpt_service.get_height() + 1:
            logger.info("Proposal rejected. Height series is not correct.")
            return False, ""
        # check origin
        if checkpoint.origin != ckpt_service.get_ckpt_id():
            logger.info("Proposal rejected. Checkpoint origin does not match the last checkpoint.")
            return False, ""
        # check if utxos are not present
        if checkpoint.get_utxos() is None:
            logger.info("Unspent transaction output list is empty.")
            return False, ""

        # check if last reward wallet amount matches the constant amount
        reward = checkpoint.get_fee_rewards()
        if reward[len(reward) - 1].value != REWARD:
            logger.info("Checkpoint fee reward does not match")
            return False, ""

        # Check if checkpoint is empty
        new_list = checkpoint.get_utxos()
        new_list.sort()
        old_list = ckpt_service.get_ckpt_outputs() + ckpt_service.get_ckpt_utxos()
        old_list.sort()

        if new_list == old_list:
            logger.info("Checkpoint rejected. Proposal is empty.")
            return False, "EMPTY"

        # check for existence of wallet in the DAG
        for output in checkpoint.get_utxos():
            status = verify_output(output)
            if not status:
                return False, ""
        # Add missing transaction id to transaction checklist
        if pending:
            for txn in pending.keys():
                missing_txn.append(txn[0])
            # add the txn to fetch list
            for txn in set(missing_txn):
                assert isinstance(txn, bytes), "txn must be bytes!"
                agentservice.add_txn_to_fetch_list(txn)
            logger.info("Few transactions were not found. Request for missing transaction sent to network.")
            return False, "PENDING"

        # check if pending list is empty
        if not pending:
            logging.info("Checkpoint proposal accepted.")
            return True, ""
