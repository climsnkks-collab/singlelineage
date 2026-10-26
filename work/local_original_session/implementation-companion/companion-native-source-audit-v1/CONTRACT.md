# COMPANION-MAGE native source seam audit v1

SOURCE_AUDIT_COMPLETE / NATIVE_ADAPTER_NOT_SUPPLIED / test_ready:false / runtime:UNRUN.

기존 제품 source에는 **호출 중 current Actor/Interaction Pair를 유지하고 재확인하는 패턴**이 있다. 그러나 서버 발급 동료 UID/generation을 원 native Player 게시에 연결하고, 그 개별 클릭 콜백을 설치·전달·퇴역시키는 구현은 이번 선정 source에서 확인되지 않았다. 실제 ATS 설정 창 interface도 공급되지 않았다. 따라서 주소·기계 ABI만으로 native adapter를 작성하지 않았다.

## 재사용할 수 있는 정확한 접점

| 선정 source | 실제 공급 범위 | 이번 기능에서 남는 부분 |
|---|---|---|
| `equipment-window/normal-window-input-v1/equipment_window_input.hpp:38,63,122` | 기존 manual owner/UI thread/busy/sequence, 현재 player/map·manager/scene Pair 확인, 원 void entry 한 번 호출, 불확정 반환 보존 | 원 15EBF0 CharacterInfo toggle 전용이다. Actor 클릭 등록·이벤트·ATS 생성 API가 아니다. `actual_layout`/`visible`도 null이다. |
| `integration-1/item-normal-current-serial348-v1/native/entry_native.hpp:156,166,297,371,403` | 원 627B0 Actor lookup·586E0 Interaction 획득, 같은 registry/Pair·component membership 재확인, B6D20 원 callback 반환까지 Flight의 owning Pair 유지, 정리 | **기존 GroundItem action9/B7DB0** 소비 전용이다. Player용 등록자가 아니며 LOCAL generation을 받지 않는다. 기존 호출은 source-bound 원 동작을 실행하므로 동료용으로 직접 호출하면 안 된다. |
| `tools/local_native_land_move_hook/land_hook.hpp:109,122` | 기존 host callback의 revoke·shared/exclusive 수명 경계와 재진입 cleanup 처리 | WH_GETMESSAGE host callback 수명이다. Interaction I70 callable 진입·교체·정리를 가두지 않으므로 native actor invoke-drain으로 재사용할 수 없다. |
| `companion-click-router-v2/companion_actor_click.py:76,118` | 실제 server record/current lease/generation을 해석하는 명시 LOCAL 4F13 route, 원 Host locked helper 호출 | 원 Player click emission·native publication receipt가 없다. 서버 TCP DRAINED가 native 소비 receipt를 만들지 않는다. |
| `actor-click-locked-v2/tools/local_original_session/companion_host.py:343,360,380` | hotkey/actor 클릭이 같은 panel/epoch/command authority를 소비한다. 이미 row operation 안인 router가 중복 lock 없이 호출 가능 | `interface.open(...layout='ATS'...)`는 주입 interface 호출이다. 원 ATS layout factory·input binding 구현이 아니다. |

`tools/local_original_session/native/command_bridge.hpp`의 ActorPins도 기존 own-player 이동 전용이다. 명령1–4·owned UI thread와 Pair retain만 있으며 per-instance callback registration이나 이벤트 consumer가 없다. 과거 Windows message 입력 방식은 현재 패킷 시험의 선행조건으로 추가하지 않는다.

## 첫 미공급: native publication binding

REA272와 같은 결손이다. `allied-publication-source-v2/allied_player_publication.py:299–303`은 4E96 wire를 만든 뒤 별도 Python `object()` generation을 가진 record를 생성한다. 이 token은 원 wire에 실리지 않는다. 다음 전체 identity를 **원 생성·게시를 실제로 소비한 시점**에서 결속하는 source/API가 없다.

- 현재 server writer/selection/lease와 그 발급 record의 UID/generation.
- 같은 current native ActorSubsystem registry와 Player의 object/control Pair.
- 그 Player에 속한 Interaction object/control Pair, 원 callback 선택·교체의 owner 실행 문맥.
- 해당 게시 instance에 대한 실제 소비 receipt. UID/주소 재조회·서버 drain만으로는 이를 대체하지 않는다.

REA271의 normal Player selector5/I88 gate를 유지해야 한다. I70만 덮어쓰는 구현, Player field65=2(usershop) 또는 Pet selector20 강제는 동료 설정 클릭을 공급하지 않는다. REA270의 Pet 조건부 4F13은 원 Player에 자동 적용되지 않는다.

## 다음 구현 단위의 구체적인 경계

다음 native 소스 담당은 **원 actor 게시/Interaction 초기화와 같은 owner 문맥의 per-instance binding** 한 단위를 먼저 공급한다. 아래는 요구 계약이며 현재 존재하는 함수명·API나 실행 가능한 stub가 아니다.

1. server의 같은 publication record와 위 native object/control identity를 원 게시 소비에 결속한다. 같은 UID의 재게시나 같은 주소 재사용은 새 instance다. 실패·미소비이면 클릭 등록을 하지 않는다.
2. 그 instance의 original selector/fallback 경로에서 실제 클릭이 동료 callback에 도달하게 연결한다. 원 callable clone/exchange/free ABI와 같은 owner 직렬화가 필요하다. callback은 동일 record를 다시 확인하며 일반 Player/상점/Pet callback은 보존한다.
3. 원 callback의 살아 있는 receiver/code를 정상 반환까지 유지하고, 실제 클릭 이벤트를 기존 scoped 소비자에게 전달한다. 기존 LOCAL 4F13을 쓰는 선택이라면 payload는 원 f1 uint32 UID 그대로이며 server가 기존 Feature에서 current generation을 해석한다. **클라이언트 native generation 결속을 server 재조회로 대신하지 않는다.** 별도 원 S2C/ATS 응답을 추측하지 않는다.
4. remove/reselection/owner-close에서 신규 callback 진입을 막고 이미 진입한 invoke의 정상 반환 또는 미확인을 분리한다. callable 해제는 그 경계 뒤에 하며, I70 clear/4E40 send·drain/registry에서 첫 UID 제거만으로 완료 판정하지 않는다.
5. 클릭 이후 실제 UI는 Host의 기존 `interface` 한 구현에 연결한다. 독립 ATS layout instance의 open/render/close와 retained panel callback/epoch 수명 producer가 아직 필요하다. CharacterInfo toggle을 ATS 구현으로 대입하지 않는다.

현재 작성 가능한 범위는 위 실제 source 파일을 부모로 삼은 후손의 설계 경계까지다. native publication/owner 직렬화 producer가 없는 상태에서 실행 adapter·가짜 receipt·새 native API를 생성하는 것은 이번 source로 뒷받침되지 않는다. 다른 server actor-config/runtime 준비는 이 감사 결과와 독립적으로 계속한다.

## 확인과 실행 경계

저장된 REA270/271/272의 MAIN_REVIEW와 지정 제품 source만 읽었다. 새 REA/decompile/runtime/RPM/game/port/Windows input/global hook/빌드/패킷 실행은 0이다. 최소 source 검색에서 기존 B6D20 소비자를 찾아 위 GroundItem 소비 구현까지 확인했다. 이 검색 결과를 저장소 전체의 부재 증명으로 확대하지 않는다.

`parents.json`은 읽은 핵심 파일의 실제 SHA256/bytes다. `manifest.json`은 이 계약과 인계만 봉인한다. product delta·실행 caller·RUN_COMMAND는 없으며 Test-ready 또는 클릭/화면 성공을 주장하지 않는다. 공용 client/ready/API와 다른 worker의 actor-config/runtime source를 변경하지 않았다.
