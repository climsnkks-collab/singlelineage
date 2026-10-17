"""Fixed genuine-key session adapter. No arbitrary keys, paths or archive writes."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import importlib.util,hashlib,struct
ROOT=Path(__file__).absolute().parents[2]
PROOF=ROOT/'tools/original_resource_proof'
PROOF_SOURCES=('api.py','run.py','tests.py')
KEY=ROOT/'work/original_resource_proof/resource-master.key'
METADATA=ROOT/'work/original_resource_proof/resource-proof.json'
PACK=ROOT/'work/standalone_boot/current-unmodified-clone/pack'
ARCHIVE_SHA='fdca1c2773abe0be5cc4014741ff0b342c6bb0e5e33ba509cf7a9caa65ba7747'
ARCHIVE_SIZE=540779033
PRODUCER=ROOT/'tools/local_bootstrap_payload'
PRODUCER_PINS={'producer.py':'318d1d72446a8a52179a5035231de2ff8476ad9cee078443055244d6ba8e799f',
    'source_contract.py':'23b5d2c2cd5a9d90a42eeab25561d01bca7a6f5ce051f24685ba8ed2b7ea6afd'}
def require(ok,reason):
    if not ok:raise ValueError(reason)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def proof_hashes():return {n:sha((PROOF/n).read_bytes())for n in PROOF_SOURCES}
def wipe(raw):
    if isinstance(raw,bytearray):raw[:]=bytes(len(raw))
class Session:
    def __init__(self,original):self.original=original;self.closed=False;self.version_emissions=0
    def __repr__(self):return '<PreservedOriginalPackSession transient; no key values>'
    def verify_preserved_pack(self):
        require(not self.closed,'closed_original_resource_session')
        proof=self.original.verify_preserved_pack()
        require(self.original.source_archive=={'name':'data_0.lcx','sha256':ARCHIVE_SHA,'size':ARCHIVE_SIZE},
            'signed_original_archive_identity')
        return proof
    def version_frame(self):
        require(self.version_emissions==0,'single_resource_version_emit')
        self.verify_preserved_pack();wire=self.original.version_frame()
        try:
            require(type(wire)is bytearray and len(wire)==76 and struct.unpack_from('<HH',wire)==(76,0x4e35)
                and wire[-2:]==b'\0\0' and b'CONTENT_MASTER_KEY'in wire,'source_resource_version_frame_shape')
            self.version_emissions+=1;return wire
        except BaseException:wipe(wire);raise
    def close(self):
        if not self.closed:self.original.close();self.closed=True
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
def load_preserved_session():
    for name,pin in PRODUCER_PINS.items():require(sha((PRODUCER/name).read_bytes())==pin,'fixed_crypto_definition_pin')
    spec=importlib.util.spec_from_file_location('_preserved_original_resource_api',PROOF/'api.py')
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    original=module.load_preserved_session()
    require(type(original)is module.OriginalResourceSession,'fixed_original_session_type')
    session=Session(original)
    try:session.verify_preserved_pack();return session
    except BaseException:session.close();raise
