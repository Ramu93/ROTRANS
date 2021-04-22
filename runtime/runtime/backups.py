import zlib
from base64 import b64encode, b64decode

compressed_genesis = """eJzt2H1ME2ccB/C7vliKLVVATdFth+LLhuj15a4tLxmOQOLWDAWSsYSsu7Z32FBbdlwLTMkCW8nQZUNcDMvMovzh
NqOCYowmwpjDQJr9YYyKdSwo0b2oS9wyR+Yyszs8E4spzx/3z7L9Prm26e9Jf9+nz3+/p3qrOyCwBBfmtzMCYcMWYTiOlRIEhmEa+fWYes53HEPT
YBteTBilHxvfx0yvZlSIHwAAAAAAAADwv9ZepNYtM5vxjq0C4w2yzUwwyAqP3jVlVeWbasqJmk0vucuJRzViXTrxhICfENgWYX1SMcwH6gMhIsrw
3kCI4VvnrDaHPA1sa6rlJoERx8Knm0aZ4Gw1qfh8h1alW5aVhb/71uzuhZaQ+KiT9i0W5mxarHjEjafYQCDUGBGaUu4+Isy33MjwbCj18uM/8VQ1
4GeEMJ/yTAL1IUaI8OwTjZPPoX0jPnsOHeWz58D4GsRHlXQOYmHOOYiVec5h/lNq5NmoR2qJ2nKqHUuzuTj0AwAAAAAAAAAA4D9Mmv9xYwkmPgAA
AAAAAAAAUomV4nq3YZfdkIUZTrTmDHL5sY35ZQaj5s9J1bZDEQGvHq3Vby44f3u425lWkHG4cOh296HM2Jfc5K83dy9KhO8Uv7y/6ud9qz+gBtei
fo9hmyN/+Mfepnq5FaPmg3sKue+231v93sib0w7KsLLG+s5VZAf863vRI3UjFcd+K2rKyus7xx+//1rN5LO9n1ZeSeRvWVfbjeygOvXt/uwbudyV
C86dxJhnvHSM+9x0YcVl9/lMP3VZ9fAnZAd17FqUPhF8Pbvs8A8l5k/iI0dvdo5f6/o9h+4c2Jnzy2djyA4a9plLByisZ8Oo47R299HqbzoKlh+p
yqyr75v5qLPu4xseZAet6cGEe0/b9313Yvfp8ZPh5Z098VWms+ou7RJuaOTclvXIDguKc3fEK7i2XqqyssScd2sqvstQfJGeeGG67Iv+meu5x5Ed
dDPZS38c6umeuD4V/yqaPkAOfrjv7sWiwsQrfxF79S0DbcgOaYnphc4lD3P7897oGi7sP7jqQW2UHPy7+azl7o5t/squ55Ad9BaSlOb/9IXDmGmv
aU3GmQy3ccrIG7WGXkO+WAQAAAAAAAD8izSk60ztRrdpsctrdbgsjNdG01avk7JyVq/dRvpIP2nnXH4faaWdDO2gHHbSQtl8dspJuuwuq99HsYyX
dZE2J2qYIC1kg14OcyoNQ80+UliaHOZQGoYa1aQwnRxGKw1DTZZS2AI5jFIahhqEpTCtHGZXGoaa26UwjRxmUxqGumaQwtRymFVpGOpWRApTyWEW
pWGoSxwpDJfDSKVhqDsnMewf+PRBzg=="""


def create_dump(file_name):
    dump = b''
    with open(file_name, "rb") as fp:
        read_bytes = fp.read(1000)
        while read_bytes is not None and len(read_bytes) > 0:
            dump += read_bytes
            read_bytes = fp.read(1000)
    compressed_dump = zlib.compress(dump)
    encoded = b64encode(compressed_dump)
    return encoded.decode('utf-8')


def recall_dump(target_file):
    with open(target_file, "wb") as fp:
        decoded_genesis = b64decode(compressed_genesis.encode("utf-8"))
        decompressed_dump = zlib.decompress(decoded_genesis)
        fp.write(decompressed_dump)



if __name__ == "__main__":
    # print(str(create_dump("../genesis.db")))
    recall_dump("genesis.db")