import logging

def get_logger():
    logging.basicConfig(
        filename="app.log",
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        force=True
    )
    
    return logging.getLogger(__name__)

# a = "t"
# b = None

# print(id(a), id(b))

# if a is not b:
#     print("hi")
# else:
#     print("e")
