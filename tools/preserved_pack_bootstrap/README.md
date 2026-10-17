# 원래 signed pack 보존 bootstrap

현재 원본 게임에 맞는 resource master를 `tools/original_resource_proof/api.py`의 검증된 API로만 읽고 실제 signed clone pack의38개 LCDT를 재인증한다. 기존 ZIP·manifest·resource.key·SDK·EXE·시험 slot은 쓰지 않는다. 원본게임/PURPLE 기동·RAM capture·UAC·방화벽 조작 기능도 없다.

사용자는 게임 resource master의 **고정 로컬 plain32 파일 보관**을 선택했다. 이는 계정/password/token/SDK signature를 보관하는 기능이 아니다. 키 값·키 fingerprint·Base64·packet bytes는 stdout·로그·argv에 출력하지 않는다. `session_adapter`는 새 키를 만들지 않고 fixed API가 제공한 `OriginalResourceSession`만 사용한다. load/emit 전에 original `data_0.lcx` SHA `fdca1c2773abe0be5cc4014741ff0b342c6bb0e5e33ba509cf7a9caa65ba7747`/540,779,033B와 signed metadata·catalog·38개 auth를 API로 확인한다. mutable76B VERSION frame은 전송 직후 wipe하며 세션도 종료 시 wipe한다. 승인된32B 로컬 파일은 계속 보존한다.

기본 `python -I -B tools/preserved_pack_bootstrap/broker.py`는 Plan만 출력한다. 고정 key/proof 파일을 로드하거나 socket/native pin을 열지 않는다. Root가 fresh proof/capture 완료와 actor review를 발행한 다음 `broker.py --run`을 실제 실행한다. 임의 key/path/PID/host/port/credential CLI는 없다.

실제 실행은 source3개·original proof source3개·review·protocol9개·source contract·exact ROOT_MOUNT374691 client·plain key32/proof metadata·crypto 정의2개·pack metadata5개/data_0.lcx를 canonical single-link read-share pin으로 유지한다. reparse/hardlink/native path unknown이면 거부한다. Root review는 아래 `approved()`의 정확한 schema/필드를 사용하며 worker가 승인 파일을 대신 작성하지 않는다. 일반 권한 실행이므로 추가 UAC가 없다.

서버는 Windows SO_EXCLUSIVEADDRUSE로 **127.0.0.1:12000**만 bind한다. 점유되면 retry/foreign process kill 없이 REFUSED다. listener 최대300초, 한 클라이언트 최대120초/idle15초/입력64KiB다. initial KEY(4e20)→정확한 build/encoding VERSION request(4e34)→auth38 original key가 담긴 VERSION76B(4e35)→COUNTS(4f3d)→검토된 empty ACK(4f3e)만 지원한다. C2S 최대2/S2C 최대3 frame이며 반복/순서오류/unknown opcode/auth·login 요청은 응답하지 않고 닫는다. 인증 계정/session을 만들거나 SDK/ready/callback 플래그를 변경하지 않는다.

메타데이터는 opcode/frame size/protocol state/ACK sent만 기록한다. TCP write와38개 resource auth가 실제 게임의 처리·준비·캐릭터 진입 완료를 뜻하지 않는다. full dynamic/world closure, 독립 진입은 미완료다.

Root review schema `lc-preserved-original-resource-bootstrap-review-v1`: `reviewed/allow_run=true`, own source hashes, proof source hashes, protocol hashes, source contract hash, exact client hash, preserved archive hash, `selected_authenticated_resources=38`, fixed endpoint, `max_clients=1/max_c2s_frames=2/max_s2c_frames=3`, `key_mode=PLAIN_USER_AUTHORIZED`, `plaintext_key_storage_user_authorized=true`, `key_or_packet_values_logged/ZIP_or_manifest_writes/SDK_auth_or_ready_mutation=false`. 실행 시 파일과 review를 다시 비교한다.

검증: `python -I -B -m unittest discover -s tools/preserved_pack_bootstrap -p tests.py -v`. 합성32B·mock protocol만 사용하며 실제 key/socket/capture/game를 실행하지 않는다. 실제 작업은 Root만 한다.
