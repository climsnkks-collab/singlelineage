"""CP73 focused automatic Login OK retry after identity refusal."""
import hashlib,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PATH=ROOT/'tools/local_native_login_create_exec_runtime/binding.py'
if hashlib.sha256(PATH.read_bytes()).hexdigest()!='eebea14aeab082605f031a664bc3fc4deaafdf6ad9ccefb10fd438a21284a281':raise ValueError('FROZEN_CP06_BINDING')
s=importlib.util.spec_from_file_location('_key_invoke_binding_parent',PATH);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
for name,value in vars(m).items():
    if name.isupper():globals()[name]=value
FAMILY='LOCAL_NATIVE_LOGIN_LAND_PROBE_CP74'
CANDIDATE=ROOT/'work/local_native_login_state5_ack_candidate/native-login.candidate.bin'
MANIFEST=CANDIDATE.with_name('manifest-final.json');PREFLIGHT=CANDIDATE.with_name('candidate-preflight-final.json');PRODUCT_PINS=CANDIDATE.with_name('source-pins-final.json')
PRODUCER=ROOT/'tools/local_native_login_state5_ack_candidate/prepare.py'
CANDIDATE_SHA='656a64e7c686144615f473902590e23ce0024b907e96ad905f42e84084e8da9d';CANDIDATE_SIZE=39147520
MANIFEST_SHA='031404ef5508e71af10dd0b29b8f7a3103e1d9c982985099345dd90e123a91c8'
PREFLIGHT_SHA='c13d77b5c97260bf1fdbcbfe0a4c5d8f224e85f2f0b41958789b19c67dfbaada'
PRODUCT_PINS_SHA='d925b11383500efd0937a549adbb4f23fb5837f6b9291de3db576131ac6393a1'
DLL_NAME='own-login-bridge-cp49.dll';DLL_SHA='3a3ba64e7ce9127f7e47f442cd355ab7082aa8a4fa99edb94d97fe10b2b3333b';DLL_SIZE=75264
RUN_ID='cp74-render-20261009-01';FORWARD_RUN_ID=RUN_ID
FINALIZED=True
