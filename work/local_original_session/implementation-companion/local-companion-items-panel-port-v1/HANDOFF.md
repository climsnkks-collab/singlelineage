# COMPANION-MAGE 동료 전용 인벤토리·장비 패널 포트 v1

**WRITER_RELEASED / bounded read-only source candidate / source_ready:true / test_ready:false / run_ready:false / ui_ready:false / action_ready:false / runtime:UNRUN.**

실제 구현은 accepted ITEM port `4d2844c6…`의 Host SHA 한 literal을 현재 클릭 Host `5c561041…`로 바꾼 명시 후손이다. 기존 전체 locked read와 constructor AST는 같다. 소비하는 Host `command`, `_row`, `_state`, `view`, `_refresh_panel` 다섯 메서드도 이전 account Host와 AST가 같다. 새 wrapper/ITEM writer/장비 초기화/공용 수정은 없다. exact parent/source/reference pin은 parents.json, 한 줄 delta는 companion_item_target_view.py.diff다.

원 provider.bind_companion → BatchStore.restore → provider.current를 통해 실제 동료 UID의 account member inventory를 frozen snapshot으로 읽는 계약을 보존했다. 원 panel/epoch/active lease·actor·owner, direct generation/frame/row와 동일 계정 원 issuer 검사를 그대로 둔다. selected 플레이어 인벤토리/profile/current와 canonical CAS/Gear/adoption/current/owner 검사는 바꾸지 않았다. parent DTO 검증 결과는 재사용했고 fake Host/provider/Store로 새 통과를 만들지 않았다.

## 정확한 미완 경계

1. 현재 Host556은 `await interface.open_items(panel, kind, character_lease=active.lease, actor=active.actor, owner=active.owner)`를 요구한다. **실제 final typed interface SourceModule와 해당 본문/패널 수명 소비자가 공급되지 않았다.** constructor는 바로 이 실제 interface의 bound method와 source globals/code/path를 요구한다. 따라서 이 source 파일 존재만으로 설치/OPEN을 주장할 수 없다. UI가 완성된 것처럼 interface None 대신 임의 객체를 넣지 않았다.
2. 원 포트는 cold unstarted Host graph에만 설치된다. 계정 ATTACHING 전이에서 새 Host/provider가 발급되므로 old 인스턴스 재사용은 허용되지 않는다. 향후 actual graph가 runtime install을 요구하면 original scope token을 보유하는 명시 후손이 필요하며, 현재 guard를 완화하지 않았다.
3. 장비 읽기/변경은 미공급이다. 기존 실제55 whole-input의 UID2에는 GearState가 없으며 companion-account-equipment-input-v1의 inspection을 재사용한다. CREATE32의 legacy UID2는 다른 class0/name 계보다. 이를 class3 mage에 접붙이지 않았다. reference canonical GearStore365의 restore→_canonical_state는 batch.gear_current_locked를 호출하지만 selected Core86에는 해당 메서드가 없다. legacy sidecar나 숫자 UID 일치만으로 현재 GearState/adoption 권위가 되지 않는다.
4. reference ITEM/Gear effect `_context`는 selected scope UID/profile/generation과 original ItemUseSession projection을 요구한다. 동료 쓰기 admission이 없는 상태에서 이 내부 handler를 호출하거나 root selection/current를 치환하지 않았다. read snapshot의 action_admitted/native_opened는 false다. Use/Equip/이동/저장 API를 발명하지 않았다.
5. native selected-model-pair-v2의 encode_display는 이름/레벨/phase/reason/support만 인코딩한다. ITEM frame/장비/변경 request는 없다. 최신 display-publication-v2도 표시 primitive이며 settings UI나 command/ITEM admission이 아니다. 이 candidate는 그 native graph를 선택/수정하지 않는다.

첫 직접 blocker는 1의 actual interface이다. 뒤 조건은 독립적인 실제 쓰기·장비·수명 의존이며 이 읽기 후보로 해소했다고 주장하지 않는다. 전체 패널 및 동료 소유 장비 변경/저장 완료는 아니다.

## 확인·자원·다음 행동

`python -B work/local_original_session/implementation-companion/local-companion-items-panel-port-v1/verify_source.py` PASS. exact pins, 한 literal delta, source compile, 원 port AST와 소비 Host 다섯 메서드 AST, 원 DTO PASS 재사용 및 mutation/send/adoption 추가0만 확인했다. 실제 issuer/lease/current/Store restore/gear/action/UI는 UNRUN이다. 기존 actual55 PASS는 account custody 근거만 재사용하며 동시 companion item 요청/장비/UI PASS로 확대하지 않는다.

main은 실제 delta와 핀을 검토해 이 후보를 수용할 수 있다. 이후 actual final interface가 원 row-operation 안에서 직접 읽고 실제 표시 소비를 수행하도록 결합한다. 쓰기는 ITEM/GEAR가 실제 class3 UID2의 same-profile state·정상 authority/packet flow를 공급한 후 같은 UID·원 CAS로 연결한다. 불명확한 최종 행동은 선송하지 않는다. game caller/RUN_COMMAND:null, 시험 큐 등록0.

이 새 private 폴더만 작성했다. 원본/common/계정/Store/Test/queue/ACTIVE/기존 소스와 dirty checkout은 보존했다. 게임/서버/socket/포트/focus/입력/REA/Store copy/Factory 생성/상품·UID 발급0, branch/worktree/commit0. writer·실행 자원0.
