from ove.ove.ove_magic import OVEMagic


def load_ipython_extension(ipython):
    ipython.register_magics(OVEMagic)