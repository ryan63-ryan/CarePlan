# Known Trade-offs / Future Improvements

## Day 6: Polling 没有超时
- 现状:前端每 3 秒轮询一次,直到 status 变 completed 或 failed
- 风险:如果任务卡在 processing 永远不结束(worker 挂死等极端情况),
  前端会无限轮询
- 暂未处理原因:MVP 阶段;正常情况下 care plan 1-2 分钟内必定 completed 或 failed
- 后续改进:加一个 5 分钟上限,超时后停止轮询并显示"超时,请重试"

## 已知的"半成品"
- serializers.parse_order_input 没翻译 dob 字段 → DOB 重复检测对 CVS 数据形同虚设
  - Day 8 引入,Day 9 翻译诊所/药企数据时已经接通 dob
  - 等 Day 9-10 完成 Adapter 后,可以统一补 serializer 也接通