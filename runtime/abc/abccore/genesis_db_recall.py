import zlib

compressed_genesis = b'x\x9c\xed\xd7\xbfk\x13a\x1c\xc7\xf1\xe7i\x12\x02\xd2\xa4\xc1\x0e\xa1B\xf1\x04\x7f\x15\xc4AA\x84\x0c\xda\x96\x0cB\x87F\x0b\x8e\xe1\xb9\xf4\xd43\xe7%\xde=M\x1a\xacC\xe2\xa0\xa3\x8b\xce\xea \xe2\xde\x8a\x0e\n\xea\xe2&"\x0e:\x89 \xce\xfe\x03\xfa\xe4\x97\x98\xb4\x97Nb)\xef\x17\xcf\xe5\xc2\xf7K\x8e\xcf\xf7\xf2,\xcf\x85\xc2\x82\xab\x1d\xebR%\xb8\xa6\xb4uRd\x84\x94\xe2\xace\t!\x12\xbd\xab/\xde\xbb\xfa\xa4\xd8^B\x1c\x9f\x7f\x93j\xff0\xb5WL\x1cN\xdfK\xbd7_\x00\x00\x00\x00`Gh\xe6\xe2\xc9\xec\xd4\x94l\x15\xb4\xb2=\xa7\xae<\xcf\xd1\xdd\xcf\xc4\xfc\xf9\xfc\xecR\xdeZ\x9a\x9d[\xc8[\xdd\x9aut\x8f\xf5\x17w\xd9\xd2\xce\xaa>6P\xac\x04\xeee\xd7\xb7j*\xb0]_\x05\x8d\xa1n\xdd/\x96\x9dFT;\xd4\xca\x1c\xd06?\xb4\xa6\xbcNu\xa08\xd3\x9c\x8b%\xb3\x93\x93\xb2U\xee\xa4\xd7\xab\xbeY\xf1\x81\xdc\xa60\x14\xdaT\x8a&xD\x00\xd7\xaf\xae\xe802\xfd\x8a\x1e\xd5\xae\xaa\xc0\xf1\xa3\xdb\x11C\xa4\xc7\xbaC\xc4:C\xa8R\xd9\xac\xd8\xc0\x10\xa604\x84\xa9\x8c\x18b\xf4\x88\xd5\xc0\xa9\x15\xdb\x8f\xfc\xd3\x1f\ntQ&\xb3\xd3\xd3\xf2\x96\xec\x06\xb2K\xc5e\xa5U\xff>6\x18\xadW\x1d\xcag\xfe\xe2\xd0l\x97\x88\x04\xb6\xf2\x94_r\xa2\xda\x9e\nu\'\xe0\xe6}`\xf6Gy\xab\xfd\xa1\x03\xe5\x87\xaa\xa4\xdd\x8a_\xbc\xe2\x86\xba\x124\xb6x\xd5\xed\xb3\xb9\x9cX\x17f\x01\x00\x00\x00\x00\x80\x9d\xe4\x9cL63\xe3\xc6\xedCw\x1f?\xfbe\xbf\x9c\xf9\xf8BW\x9f\xd6\xc7\xf7\xaf\xad\x9d8\xd0\xfar\xea\xcc\xb7\xc5\xc2\x8d\x9b\xcd}9qp\xe3\xdd\xa3\x8d\x07\xd7?\x9d~\xbbx\xb5\xfe\xf0\xf5\x9d\xe4\x8f\xf5\xe7\xdf?\xdc\x7f\xf5\xf9\xa7L?9\xf25\xd7>\xff\x8b\xcc\xff\x1e\x08\x00\x00\x00\x00\x00\xfcK\x9c\xff\x01\x00\x00\x00\x00\xd8\xfd8\xff\x03\x00\x00\x00\x00\xb0\xfb\xfd\x06!^\xf2%'

def create_dump(file_name):
    dump = b''
    with open(file_name, "rb") as fp:
        read_bytes = fp.read(1000)
        while read_bytes is not None and len(read_bytes) > 0:
            dump += read_bytes
            read_bytes = fp.read(1000)
    compressed_dump = zlib.compress(dump)
    return compressed_dump


def recall_dump(target_file):
    with open(target_file, "wb") as fp:
        decompressed_dump = zlib.decompress(compressed_genesis)
        fp.write(decompressed_dump)




if __name__ == "__main__":
    # print(str(create_dump("abc_save.db")))

    recall_dump("abc_save.db")