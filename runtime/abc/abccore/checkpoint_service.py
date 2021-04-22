import logging
from decimal import Decimal
from typing import List, Tuple, Dict, Union

from abccore.DAG import Wallet, Genesis, Checkpoint
from abccore.prefix_tree import Tree

logger = logging.getLogger(__name__)


class CheckpointService:
    checkpoint = None

    def set_checkpoint(self, dagtree: Tree):
        pass

    def get_ckpt_id(self) -> bytes:
        pass

    def query_checkpoint(self) -> None:
        pass

    def stake_sum(self) -> Decimal:
        pass

    def delegated_stake(self, pb_key: bytes) -> Decimal:
        pass

    def owned_wallets(self, pb_key: bytes) -> List[Wallet]:
        pass

    def get_height(self) -> int:
        pass

    def generate_checkpoint(self, dag: Tree, length: int, miner: bytes) -> None:
        pass

    def save(self, ckpt: Checkpoint) -> bool:
        pass

    def extract(self, ckptid: Union[bytes, int]) -> Checkpoint:
        pass

    def ckpt_save(self,ckpt: Checkpoint):
        pass

    def ckpt_extract(self) -> Checkpoint:
        pass

    def get_ckpt_utxos(self) -> List[Wallet]:
        pass

    def get_ckpt_outputs(self) -> List[Wallet]:
        pass

    def get_stake_owners(self) -> List[bytes]:
        pass


class CheckpointServiceMock(CheckpointService):

    def __init__(self, dag: Tree):
        self.owners: Dict[bytes, Tuple[List[Wallet], Decimal]] = {}
        nodes = dag.get_all()
        for n in nodes:
            if isinstance(n, Genesis):
                self.process_genesis(n)
        self._stake_sum = Decimal(0)
        for owner in self.owners:
            self._stake_sum += self.delegated_stake(owner)

    def process_genesis(self, genesis: Genesis):
        logger.info("Processing genesis.")
        for wallet in genesis.outputs:
            owner = wallet.get_pk()
            if owner not in self.owners:
                self.owners[owner] = ([], Decimal(0),)
            owned_wallets = self.owners[owner][0]
            owned_wallets.append(wallet)
            owned_money = self.owners[owner][1]
            owned_money += wallet.value
            self.owners[owner] = (owned_wallets, owned_money)

    def stake_sum(self) -> Decimal:
        """
        returns the current sum of all stake in the system.
        """
        return self._stake_sum

    def delegated_stake(self, pb_key) -> Decimal:
        """
        return stake that is delegated to the given public key.
        """
        if pb_key in self.owners:
            return self.owners[pb_key][1]
        else:
            return Decimal(0)

    def owned_wallets(self, pb_key) -> List[Wallet]:
        if pb_key in self.owners:
            return self.owners[pb_key][0]
        else:
            return list()

    def get_stake_owners(self) -> List[bytes]:
        validators = list()
        for owner in self.owners.keys():
            stake_total = self.delegated_stake(owner)
            if stake_total >= 0.0:
                validators.append(owner)
        return validators

if __name__ == "__main__":
    import agent

    a = agent.Agent()
