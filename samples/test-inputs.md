# Test inputs for prompt review

Deliberately messy, in the ways real CVs are messy. Run them with:

    python scripts/sample_run.py

which writes `samples/last-run.md` — original and rewrite side by side for
every case and register. Read that file, not the model's reputation.

## What to check in the output

- **Register** — does `formal` actually read more conservative than `tech`, or
  did the model produce the same Arabic three times? If the registers collapse
  into one voice, the register blocks in the prompt are too weak.
- **Invented facts** — numbers, durations, team sizes, tools that were not in
  the input. This is the failure that matters most; a fabricated metric on a CV
  is worse than an awkward sentence.
- **Masdar form** — do bullets start with إدارة / تطوير / الإشراف على, or did
  the model produce first-person past-tense verbs (كنت مسؤولاً، قمت بـ)?
- **Calques** — in `tech`, did it force "التعلم الآلي" where "machine learning"
  should have stayed? In `formal`, did English leak through?
- **Numerals** — Western digits (30%) or Arabic-Indic (٣٠٪)?
- **Bullet count** — same number in and out, no padding.

---

## 1. Egyptian dialect, heavy English mixing

```
كنت مسؤول اني اظبط الـ database و اعمل backup كل اسبوع
شغلت على الـ migration بتاع الـ system القديم للـ cloud و خلصناه في 3 شهور
ساعدت اننا نقلل الـ downtime حوالي 30%
```

## 2. Pure Egyptian dialect, no English

```
اشتغلت في خدمة العملاء تلات سنين و كنت بترد على الشكاوى
ظبطت نظام جديد للرد خلى الوقت يقل من يومين لنص يوم
دربت 6 موظفين جداد
```

## 3. Pure English, needs Arabic output

```
Led a team of 8 engineers delivering a payments integration for a regional bank
Reduced infrastructure cost by 22% through migration to containerised workloads
Owned the incident response process and cut mean time to recovery from 4h to 45m
```

## 4. Already formal Arabic — should be lightly improved, not rewritten wholesale

```
قمت بإدارة فريق المبيعات في المنطقة الشرقية وتحقيق نمو في الإيرادات بنسبة 18%
كنت مسؤولاً عن إعداد التقارير الشهرية ورفعها إلى الإدارة العليا
```

This case tests restraint. If the model "improves" facts that were already
correct, or inflates 18% into something else, the fact-preservation rule is not
holding.

## 5. Mixed script inside single sentences, job titles in English

```
اشتغلت account manager في Vodafone من 2019 لـ 2022
كان عندي 15 client و حققت الـ target كل quarter
عملت present للـ board مرتين في السنة
```

## 6. Vague input — the hardest case

```
كنت بساعد الفريق في حاجات كتير
عملت شغل كويس في المشاريع
```

There is nothing here to quantify. Correct behaviour is a clean, honest,
still-vague MSA bullet. If the model produces "قيادة فريق مكوّن من 10 أعضاء"
out of this, the prompt is not holding rule 1 and needs tightening before
anything else in the project moves forward.

## 7. Over-length / paragraph form

```
انا خريج هندسة حاسبات ٢٠١٨ و اشتغلت في شركتين، الأولى كانت startup صغيرة
عملت فيها frontend بالـ React و الثانية شركة كبيرة عملت فيها backend
بالـ Node.js و كنت جزء من فريق ٢٠ مهندس و عملنا نظام بيخدم ٥٠ ألف مستخدم
```

Tests paragraph-to-bullet splitting, and whether Arabic-Indic numerals in the
input (٢٠١٨، ٥٠) come back as Western digits in the output as rule 5 requires.
