from decimal import *
from abccore.DAG import *


def outputs_helper(inputs, outputs):
    """Adds remaining value of input wallets to outputs after calculating fee based on :param outputs.
    See Issue #16 for more information.
    The function first calculates the fee for the transaction based on :param inputs and :param outputs, just like
    agent.is_valid_function() does, but it calculates the remaining value of the wallets in :param inputs, too.
    Then, the public keys of wallets in :param inputs will be used to create new wallets for the remaining value
    starting at the last wallet in the list :param inputs. This is to ensure that the remaining value won't be subject
    to the transaction fee as proposed in Issue #14.
    :param inputs: list of wallets to be spend in a transaction.
    :param outputs: list of wallets to be paid without own wallets for remaining value, those will be created here.
    """
    in_sum = Decimal(0)
    out_sum = Decimal(0)
    inputs_dict = {}
    taxed = Decimal(0)
    for wallet in inputs:
        in_sum += wallet.get_value()
        if inputs_dict.get(wallet.get_pk()) is None:
            inputs_dict[wallet.get_pk()] = wallet.get_value()
        else:
            inputs_dict[wallet.get_pk()] += wallet.get_value()

    laundering = (
        True  # if the output wallets only redistirbute money between the input wallets
    )
    for wallet in outputs:
        out_sum += wallet.get_value()

        if (
            inputs_dict.get(wallet.get_pk()) is None
            or inputs_dict.get(wallet.get_pk()) < wallet.get_value()
        ):
            taxed += wallet.get_value()
            laundering = False

    if laundering:
        taxed = in_sum

    fee = calculate_fee(taxed)
    remaining_value = in_sum - (out_sum + fee)
    while not remaining_value <= 0:
        key_value = inputs_dict.popitem()
        if key_value[1] > remaining_value:
            outputs.append(Wallet(key_value[0], remaining_value))
            remaining_value = 0
        else:
            outputs.append(Wallet(key_value[0], key_value[1]))
            remaining_value -= key_value[1]

    if is_valid_trans(inputs, outputs):
        return outputs
    else:  # Error Handling
        msg = "Didn't create valid outputs for this inputs: ["
        is_valid_trans(inputs, outputs)
        for wallet in inputs:
            msg += str(wallet) + ", "

        msg += "]. Got instead this: ["
        for wallet in outputs:
            msg += str(wallet) + ", "

        msg += "]."
        raise Exception(msg)
