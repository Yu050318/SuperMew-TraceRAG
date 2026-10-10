# 人工复核清单

以下为待人工勾选的 10 条代表 Case；自动一致性检查不替代人工复核。

- [ ] simple_fact_001：NX-041 的安装要求是什么？
  参考：NX-041 的安装要求：断电后接线并固定在 DIN 导轨上。
  来源：product_manual.md::NX-041::section

- [ ] simple_fact_010：NX-050 的使用环境是什么？
  参考：NX-050 的使用环境：室内干燥环境，禁止浸水。
  来源：product_faq.md::NX-050::section

- [ ] table_query_001：NX-001 的额定功率是多少？
  参考：NX-001 的额定功率为 120 W。
  来源：product_specs.xlsx::产品参数::2

- [ ] table_query_010：NX-010 的额定功率是多少？
  参考：NX-010 的额定功率为 100 W。
  来源：product_specs.xlsx::产品参数::11

- [ ] cross_document_001：2026-02-01 购买的 NX-081 额定功率和保修期分别是多少？
  参考：NX-081 的额定功率为 155 W。 2026-01-01 起购买的设备保修 24 个月。
  来源：product_specs.xlsx::产品参数::82; aftersales_policy.md::2026政策::section

- [ ] cross_document_010：NX-090 的通信协议和安装要求分别是什么？
  参考：NX-090 的通信协议为 MQTT。 NX-090 的安装要求：断电后接线并固定在 DIN 导轨上。
  来源：product_specs.xlsx::产品参数::91; product_manual.md::NX-090::section

- [ ] no_answer_001：NX-901 的额定功率是多少？
  参考：知识库未提供该型号信息，无法确认额定功率。
  来源：全语料不存在此型号；需检查拒答

- [ ] no_answer_010：NX-910 的额定功率是多少？
  参考：知识库未提供该型号信息，无法确认额定功率。
  来源：全语料不存在此型号；需检查拒答

- [ ] version_policy_001：NX-001 的公告与参数表功率不同；硬件 2.0 应使用哪个数值，如何解释差异？
  参考：NX-001 的额定功率为 120 W。 NX-001 硬件 1.0 的额定功率为 130 W（2025-01-01）；2.0 自 2026-01-01 生效，以产品参数表的 2.0 数值为准。
  来源：product_specs.xlsx::产品参数::2; release_notes.md::NX-001::section

- [ ] version_policy_010：售后说明同时写了 12 和 24 个月；2026-10-01 购买适用哪个保修期，旧政策为何不同？
  参考：2025-01-01 至 2025-12-31 购买的设备保修 12 个月。 2026-01-01 起购买的设备保修 24 个月。 按购买日期适用，2026-01-01 起购买适用新政策。
  来源：aftersales_policy.md::2025政策::section; aftersales_policy.md::2026政策::section; warranty_rules.md::适用规则::section
