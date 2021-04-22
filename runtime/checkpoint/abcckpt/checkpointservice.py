import logging
import sqlite3
from decimal import Decimal
from typing import Union, List

from abcckpt.ckpt_creation_state import PreCkptStatus
from abcckpt.pre_checkpoint import PreCheckpoint
from abccore.DAG import Wallet
from abcckpt.checkpoint_db import ckpt_save, ckpt_extract
from abcckpt.ckptproposal import Ckpt_Proposal
from abccore.prefix_tree import Tree
from abccore.DAG import Checkpoint, Genesis
from abccore.checkpoint_service import CheckpointService


class CkptService(CheckpointService):
    """
    Provides checkpoint related services to the abc and checkpoint calculation functions.
    """
    checkpoint: Checkpoint = None
    pc: PreCheckpoint = None

    def set_checkpoint(self, dagtree: Tree) -> None:
        """
        Updates checkpoint service with new checkpoint.

        Parameters:
            dagtree(Tree): DAG of nodes from abc
        """
        if dagtree is not None:
            self.checkpoint = dagtree.get_latest_checkpoint()

    def get_ckpt_id(self) -> bytes:
        """
        Returns the identifier of the checkpoint object.
        """
        return self.checkpoint.id

    def get_height(self) -> int:
        """
        Returns the height of the checkpoint provided by checkpoint service.
        """
        return self.checkpoint.height

    def get_ckpt_utxos(self) -> List[Wallet]:
        """
        Returns the list of unspent outputs of the checkpoint.
        """
        return self.checkpoint.utxos

    def get_ckpt_outputs(self) -> List[Wallet]:
        """Returns the fee/reward list of outputs from the checkpoint"""
        return self.checkpoint.outputs

    def get_stake_owners(self) -> List[bytes]:
        """Returns the list of stake owners from the checkpoint"""
        validators = list()
        for owner in self.checkpoint.stake_dict.keys():
            stake_total = self.delegated_stake(owner)
            if stake_total >= 0.0:
                validators.append(owner)
        return validators

    def save(self, ckpt: Checkpoint) -> bool:
        """Saves the checkpoint into the checkpoint database

        Parameters:
            ckpt (Checkpoint): checkpoint object

        Returns:
            bool: status if saved into the database
        """
        status = False
        try:
            status = ckpt_save(ckpt)
        except sqlite3.IntegrityError as err:
            logging.info(str(err) + "DB already has checkpoint with identifier" + str(ckpt.id.hex()))
        return status

    def extract(self, ckptid: Union[None, bytes, int]) -> Checkpoint:
        """Extracts the checkpoint with given id or height from the database and returns the checkpoint object.

        Parameters:
            ckptid (bytes/int): Checkpoint identifier, it can be height or the identifier.

        Returns:
            Checkpoint: checkpoint object
        """
        return ckpt_extract(ckptid)

    def stake_sum(self) -> Decimal:
        """Returns the total stake in the system.

        Returns:
            Decimal:
        """
        return self.checkpoint.total_stake

    def delegated_stake(self, pb_key) -> Decimal:
        """Returns stake held by the validator.

        Parameters:
            pb_key (bytes): Public key of the validator.

        Returns:
            Decimal: stake held by the validator.
        """
        if pb_key in self.checkpoint.stake_dict:
            return Decimal(self.checkpoint.stake_dict[pb_key])
        else:
            return Decimal(0)

    def owned_wallets(self, pb_key) -> List[Wallet]:
        """Returns the list of wallets owned by the

        Parameters:
            pb_key (bytes): public key of the validator.

        Returns:
            list[Wallet]: list of wallets owned by the validator.
        """
        wlist = []
        for wallet in self.checkpoint.utxos:
            if wallet.origin == pb_key:
                wlist.append(wallet)

        # wallets earned from fees
        for wallet in self.checkpoint.outputs:
            if wallet.origin == pb_key:
                wlist.append(wallet)
        return wlist

    def generate_checkpoint(self, dag, length: int, miner: bytes):
        """
        This function calculates the checkpoint data and returns the generated Checkpoint.
        Parameters:
            dag: dagtree from the agent.
            length: ack length(number of transaction confirmed since last checkpoint)
            miner: public key of the checkpoint proposer.

        Returns:
              Checkpoint: Calculated Checkpoint object.
        """

        # height is incremented with new checkpoint creation
        proposal = Ckpt_Proposal(dag, self.checkpoint.get_identifier(), self.checkpoint.height + 1, length, miner, self)
        return proposal.Ckpt

    def set_pc(self, pc: PreCheckpoint) -> None:
        """
        Saves the checkpoint consensus state.

        Parameters:
            pc (PreCheckpoint): PreCheckpoint object

        """
        self.pc = pc

    def get_pc_state(self) -> PreCkptStatus:
        """
        Returns the checkpoint consensus state object.
        """
        return self.pc.state.step_status
