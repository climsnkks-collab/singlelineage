2026-10-17 · 새 원 Use callback source 후보 / 실제 실행 미검증

공개 UseItem message/request/result schema와 공통 busy·seq·terminal 정책은 frozen `manual-source-reselect`에서 그대로 사용한다. 새 `use_item::Io{}.execute`만 `owned_ui::Native`로 선택한다. `invoked`는 **A0C0B0 Use callback 시도 여부**이며 앞선 selector/getter/lookup 호출 여부가 아니다. `RETURNED`는 그 원 callback의 정상 반환만 뜻한다. 송신·서버 승인·장착·효과·render 성공을 뜻하지 않는다.

Native의 실제 소비 경로는 다음과 같다.

1. 기존 Root/ready·UI/state/scene strong Pair·현재 player/map/Inventory row 검사를 재사용한다. current manager+328 mode와 accepted55 원 FNV/bucket 조회로 실제 Inventory9 selector entry를 찾고, entry+10의 실제 string32와 entry+68 actual selector(vptr1222A28/+10=A0D5D0)를 A13B10 전에 검증한다. public cache+348/+350을 impl cache로 사용하지 않는다.
2. A13B10(out Variant72, borrowed stored key, 실제 mode)의 정상 반환에서 RAX==out을 확인한다. 같은 원 first-name string을 B3A0B0(manager,outPair16,key)에 빌려 existing impl cache+388/+390만 조회한다. 반환 strong Pair의 P vptr12228D8/TD1771848, control1222A98 및 control+10==P를 확인하고 P+30의 Q를 별도 원 intrusive 참조로 유지한다. P+8/+10 weak-self는 변경하지 않는다. ordinary/Purple key를 실제 mode/selector 출력과 구별하며 생성·setup 함수를 호출하지 않는다.
3. 실제 Q.slot3D8=B5B130, C=Q+200/C+40==Q, 원 C52840 out16/RAX 동일 주소와 entry+30 typed UIDropSlotComponent X/X+10==Q를 결속한다. C52840 output은 owning X가 아니며 X의 별도 참조는 원 count 계약으로 얻는다.
4. held Q의 실제 child hierarchy를 원 B58430(vslot1E0) field 계약으로 읽는다. X의 raw slot 값은 이 실제 child들과 비교하며, raw X pointer부터 역참조해 나중의 output owner로 소급 정당화하지 않는다. 실제 nonempty child-name sequence를 전부 사용하고 unique registered SlotNode의 UID/B0==2와 현재 Inventory UID를 결속한다. 임의 Root prefix·공용 부모·하나의 이름·escaping·raw candidate 직접 retain을 사용하지 않는다.
5. 원 allocator3C020의 size<1000h 계약으로 borrowed path string32를 준비한다. 별도 owned Q input8B와 빈 out8B로 A56810을 호출한다. RAX==out, input consume/zero, out==등록 candidate를 확인한다. 정상 owning out이 없거나 다른 Node이면 callback을 호출하지 않는다.
6. owning SlotNode를 가진 채 마지막 current owner/등록 집합을 검사하고 X의 추가 참조를 **entry 전에** 끝낸다. 이후 mutating/reentrant 원 helper 없이 actual listener/state+88==same Node, state+80 actual fn/vptr1222788/+10=A0C0B0와 현재 model UID/B0 조건을 마지막으로 결속한다. RCX=actual fn, RDX=&same owned Node8B storage로 A0C0B0 전체에 한 번 위임한다. 직접77340/4FF8E0/4FD260 호출·params/protobuf 제조는 없다. 원 Use 내부 조건·분기·pending·cleanup을 그대로 소비한다.
7. `attempted=true`는 entry 직전 설정한다. 원 UI thread·공통 seq/once·CPP/SEH 경계를 유지하며 예외는 UNKNOWN/terminal, retry/fallback/추측 cleanup은 없다. owning SlotNode는 전체 정상 RET까지 유지하고 원 ReleaseNode로 한 번 정리한다. callback이 UI에서 제거해 owner가1이 되어도 정식 output 참조의 정상 dtor ABI를 사용할 수 있다. **invoke 뒤 borrowed X/listener/state/fn을 읽지 않는다.** 독립 P/Q와 Native가 소유한 문자열·기존 snapshot 참조만 정리한다. P/Q의 원 owner 변화로 정리 조건을 확인할 수 없으면 UNKNOWN으로 남긴다.

직접 소비 guard는 A13B10/234B, 실제 selector A0D5D0/29B, B3A0B0/206B, C52840/208B, A56810/626B, A0C0B0 전체244B, 문자열 cleanup3BE90/97B와 기존 allocator3C020/16B prefix다. 각 실제 호출 시 해당 loaded image/base·exec·guard/noaccess·exact literal을 검사하며 accepted span의 연속 coverage도 확인한다. 원 Data6범위는 별도 read-only literal guard다. **old150/2116 구현과 old 직접 binding은 원 파일에 보존하지만 새 위임 route의 의무 선행조건으로 자동 복사하지 않는다.** 취소된598C0 source/guard·factory·등록·페이지 변경/warmup은 없다. 상위 entry가 자식 NoAccess를 해결한다는 보장은 없다.

범위를 넘거나 ambiguous한 현재 값은 엄격히 거부한다. bucket 순회128, child array/raw slot512, 전체 tree 방문2048/depth16, 이름128B/path255B가 상한이다. 빈 이름·dot 포함 이름·중복 sibling name은 해당 path로 선택하지 않는다. zero-token의 Q 반환을 원하는 SlotNode로 해석하지 않는다. 이런 제한을 만족하는 현재 path의 존재, cache hit가 active UI라는 결론, opaque model의 전체 class/업무명은 주장하지 않는다.

추가 reason의 정확값은 Prefix61, Selector62, SelectorType63, VariantCall64, VariantResult65, ImplEntry66, ImplCall67, PcType68, QOwner69, ComponentCall70, ComponentType71, Cleanup72, Changed73, SlotPath80, PathStorage81, NodeLookup82, NodeOutput83, SlotTuple84, UseEntry85, DirectCodeBase24000+직접 literal index다. enum의 이전 reason60은 이 새 정상 route에서 반환하지 않는다. 기존 u32 result field를 사용한다. path·same output·tuple 조건 불충족은 BLOCKED_SOURCE_BINDING, 명확한 entry/getter guard 실패는 CODE_ANCHOR_BLOCKED이며 어느 경우에도 직접 sender fallback은 없다.

accepted33/39/48/51/52/53/54/55/56의 source/검토를 재사용했고 새 source 조사·REA·decode·PE 분석·게임 실행은 하지 않았다. 실제 현재 path/entry protection·원 callback 실행·CS0960·효과·화면은 모두 UNKNOWN이다. main의 source 후보 수용 이후 통합이 실제 단일 축소 기능 시험을 소유한다.
