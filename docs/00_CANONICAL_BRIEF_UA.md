# QUALOR
## Canonical Foundation Brief v1.0
### Autonomous Opportunity Intelligence

**Find what qualifies. Pursue what matters.**

Канонічний фундамент продукту, архітектури та конкурсної реалізації.

**Власник:** Rostyslav Brenych / Brenych Studio  
**Дата базової редакції:** 5 вересня 2026 року  
**Часовий пояс планування:** Europe/Madrid  
**Документ:** QUALOR-FOUNDATION-01  
**Статус:** назву й варіант A затверджено; деталізований baseline v1.0 підготовлено до review.  
**Реалізація:** не розпочата цим пакетом. Жодного deployment, cloud provisioning, публікації чи подання заявки не виконано.

---

## 00. Як користуватися цим пакетом

Цей документ є головним джерелом продуктового наміру та архітектурних меж. Він не є рекламним описом, гарантією перемоги чи доказом уже реалізованих можливостей. Усі функції нижче — вимоги до майбутньої реалізації, якщо прямо не зазначено інше.

Порядок читання: цей бриф → `01_ROADMAP_AND_GATES.md` → `02_REQUIREMENTS_AND_EVALUATION.md` → `03_DECISIONS_AND_RISKS.md` → `04_DEVELOPMENT_HANDOFF.md`. Перевірені зовнішні факти та їхні обмеження зібрано в `05_VERIFIED_SOURCES.md`. Поточний стан ведеться в `06_PROJECT_STATUS.md`.

**Ієрархія рішень:** письмове рішення власника → прийнята версія брифу → ADR із явним посиланням на зміну → roadmap → конкретний Codex task → результат із доказами. Результат виконання не може самовільно змінити вимоги. PDF і DOCX — читабельні експорти; редагований канон — Markdown.

**Уже погоджено власником:** назва QUALOR; один автономний Strands agent з детермінованим контрольним шаром; evidence-first підхід; людське погодження; окремий чесний конкурсний проєкт; використання наявного AWS-акаунта без створення другого; відсутність залежності від схвалення заявки на $1,000.

**Уточнення цього baseline:** тризначна перевірка невідомих умов; відокремлення рейтингу від шансів; контроль витрат у застосунку; захищений live-доступ; версійність доказів та approval. Ці уточнення не змінюють варіант A, але мають бути враховані під час приймання брифу.

## 01. Суть продукту

QUALOR — автономний агент для засновників і малих технологічних або креативних команд, який перетворює потік конкурсів, грантів і програм підтримки на коротку чергу обґрунтованих рішень. Він знаходить кандидати, читає офіційні правила, зіставляє їх із профілем команди та портфелем проєктів, виділяє блокери й готує матеріали для наступного людського кроку.

Продукт не має максимізувати кількість знайдених посилань. Його ціль — зменшити непродуктивні витрати часу й кількість помилкових рішень. Відмова від красивої, але непридатної програми є корисним результатом нарівні зі знайденою можливістю.

**Головна обіцянка:** «QUALOR знаходить можливості, перевіряє, чи вони вам підходять, і приносить лише ті рішення, які заслуговують вашого часу».

**Одне речення для англомовної презентації:** “QUALOR discovers and qualifies opportunities against your real projects, shows the evidence and blockers, and prepares the next step for your approval.”

QUALOR не є універсальним чатботом, юридичним консультантом, автоматичною системою подання заявок або передбачувачем перемог. Він допомагає ухвалювати рішення за наявною інформацією та відкрито показує її межі.

## 02. Проблема, аудиторія та перший користувач

Засновник мусить шукати програми, читати довгі правила, перевіряти географію, юридичну форму, технічний стек, походження коду, ліцензію, дедлайн та реальну цінність призу. Ці дані розкидані між анонсом, FAQ, сторінкою правил і формою заявки. Короткий пошуковий результат може пропустити саме той пункт, що робить участь неможливою.

Основна аудиторія V1 — solo founders і команди приблизно з 1–5 людей, які мають кілька прототипів або продуктів, обмежені гроші та час. Другорядна аудиторія — невеликі студії, незалежні розробники та creative-tech команди. Enterprise grant management, консорціуми й університетські research offices не є ціллю конкурсної версії.

**Перший dogfood-профіль — Brenych Studio.** За повідомленням власника, немає бюджету на відкриття компанії; є наявний AWS-акаунт і близько $200 кредитів; заявка на $1,000 очікує рішення, ще $50 можуть бути надані конкурсом. Це user-reported контекст, а не перевірений billing balance. Кредити не трактуються як готівка чи інвестиція.

Вхідний профіль містить країну проживання, юридичний статус, склад команди, доступний час, обмеження витрат, готовність відкривати код і поточні участі. Невідомі факти не виводяться з назви студії, сайту чи громадянства. Відсутність зареєстрованої компанії не перетворюється на вигаданий legal entity.

Портфель може включати Weekfield, BDB, Native Site Control, Living Atlas та інші проєкти, але лише за явно введеними описами. Агент не отримує доступу до їхніх приватних репозиторіїв. Стадію, користувачів, виручку, ліцензію й доступність коду не можна вигадувати. Публічний demo використовує окремий синтетичний або знеособлений профіль.

## 03. Бренд і позиціювання

**Канонічна назва:** QUALOR. У звичайному тексті припустимо Qualor; repo, package slug і resource prefix — `qualor`. ScoutOps залишається тільки історичною назвою концепції, а не alias у коді.

Назва створена як брендова асоціація з qualification і value; це не словниковий переклад і не твердження про латинське походження. Попереднє прийняття назви не означає перевірену свободу торговельної марки, домену чи package handle. Публікація package та купівля домену не входять у bootstrap.

Підзаголовок — **Autonomous Opportunity Intelligence**. Основний акцент у комунікації — на підтвердженій відповідності, економії уваги та наступній дії. Не використовувати обіцянки «гарантоване фінансування», «точні шанси перемоги», «юридично схвалено» або «всі можливості інтернету».

Зв'язок із Brenych Studio показуємо як авторство продукту, а не як юридичну форму чи партнерство зі спонсором. AWS, Strands та моделі згадуються як використані технології лише після реальної інтеграції. Їхні логотипи не мають створювати враження офіційного endorsement.

## 04. Ціль конкурсу та обмеження

Ціль — конкурентоспроможний завершений submission у напрямі **Professional Agents**. Це наша обрана стратегія, а не оцінка ймовірності виграшу. Внутрішній критерій успіху незалежний від призу: відтворюваний агент, який реально корисний для власної роботи.

Перевірені конкурсні вимоги й календар наведено у джерелах S01–S03. Наш внутрішній submission target — **13 вересня 2026, 18:00 Europe/Madrid**; остаточний дедлайн організатора відповідає **15 вересня, 02:00 Europe/Madrid**. Буфер не призначений для нових функцій.

**Часовий ліміт:** до 40 годин сфокусованої роботи на bootstrap, реалізацію, QA та submission; орієнтир — максимум п'ять робочих днів, а не п'ять днів безперервної роботи. Це ліміт планування, не обіцянка строку. Зовнішнє очікування доступів не збільшує дозволений обсяг задач.

**Фінансова рамка:** ціль $15–25 валових сервісних витрат QUALOR, плановий максимум $40 з резервом. Це не гарантія рахунку AWS й не дозвіл списувати готівку без перевірки кредитного покриття. У межах спільного акаунта не зупиняти та не змінювати інші продукти.

Принцип роботи: спершу доказ цінності та доступності інтеграції; потім оформлення. Один сильний сценарій важливіший за широку матрицю частково готових функцій.

## 05. Межі конкурсного MVP

**Обов'язкове ядро:** один founder profile, до п'яти проєктів; керований live discovery; читання офіційних сторінок; структуровані claims з джерелами; eligibility gate; відповідність проєкту; коротке пояснення витрат і вигоди; рішення APPLY / PREPARE / WATCH / SKIP; історія запусків; локальний readiness brief; людське погодження створення розширеного draft pack.

Друга обов'язкова властивість — **повторний запуск із порівнянням**. Незмінена можливість не породжує новий actionable alert. Зміна дедлайну, eligibility або вимог показує, що змінилося і чому потрібне нове рішення. Це має працювати на двох запусках, а не лише в презентаційному тексті.

**Межа V1:** пошук і кваліфікація можливостей для software / AI / creative-tech команд. Гранти й акселератори включаються лише настільки, наскільки їхні публічні правила доступні та зрозумілі. Складні правові тлумачення повертаються на review.

**Відкладено:** SaaS billing, багатокористувацькі ролі, OAuth до пошти, CRM, mobile app, browser extension, RAG/vector DB, автоматичне заповнення зовнішніх форм, платежі, документи з персональними фінансовими даними, multi-agent swarm, власна пошукова індексація й повноцінний scheduler.

**Опційно після зеленого ядра:** один schedule trigger та обмежений browser fallback; managed evaluations; до трьох технічних статей. Ці роботи відпадають першими при ризику дедлайну. Gateway для підтвердженого AWS Web Search не є опційним, якщо обрано саме цю інтеграцію; будь-які інші Gateway-функції не додаємо без потреби.

## 06. Канонічні користувацькі сценарії

**J01 — знайти наступну розумну дію.** Користувач підтверджує профіль, проєкти й ліміт одного запуску. Агент сам обирає пошукові запити, читає джерела, виконує обмежену перевірку й завершує run з коротким inbox. Для кожної рекомендації видно відповідний проєкт, факти, блокери та наступний крок.

**J02 — не витратити час на непридатний конкурс.** У синтетичному кейсі програма вимагає incorporated company, а профіль — individual. QUALOR показує FAIL за конкретною умовою і SKIP із поясненням. Великий cash prize не підвищує це рішення до APPLY. Це тестовий сценарій, а не твердження про нову реальну програму.

**J03 — чесно зупинитися на невідомому.** Landing page дозволяє teams, але правила юридичного статусу недоступні. QUALOR не робить PASS із мовчання: ставить REVIEW_REQUIRED, перелічує невідомі умови та пропонує питання організатору.

**J04 — підготувати пакет після погодження.** Користувач погоджує draft для конкретної версії можливості й профілю. Агент створює локальний package: опис, відповідність вимогам, checklist, список відсутніх матеріалів і supporting sources. Нічого не надсилається організатору.

**J05 — побачити тільки суттєву зміну.** Другий запуск не дублює незмінені записи; ранній дедлайн або нова вимога open-source скасовує актуальність попереднього approval й створює нове рішення. Попередня історія залишається доступною.

## 07. Варіант A: архітектурний канон

Архітектура складається з одного керованого Strands agent і контрольного шару, який не довіряє моделі остаточні права, бюджети та статуси. Агент визначає наступний інформаційний крок; детермінований код визначає, чи дозволений цей крок і чи достатньо доказів для рішення.

Потік: **Profile → Run Controller → Strands Agent → bounded tools → Evidence Store → Rule Engine → Decision Engine → Inbox → human approval → Draft Pack**.

Контрольний шар відповідає за typed validation, ліміти, таймаути, idempotency, стан, evidence references, підтримані правила, policy versions і перевірку approval. Модель формулює запити, витягує кандидати правил, обґрунтовує match і пише текст на основі дозволених фактів. Вона не може змінити ліміт, підтвердити власний approval чи зробити зовнішню submission.

**Локальний контур:** Python backend + CLI; SQLite; локальний evidence directory; React UI, прив'язаний через backend до поточного run. Це основний шлях розробки й відтворення.

**Конкурсний cloud-контур:** той самий domain core і Strands logic в AgentCore Runtime; Bedrock model; AgentCore Gateway/Web Search; S3 для невеликого приватного state/evidence набору. Для демо дозволено лише одного writer. S3 persistence є окремим adapter, а не новим domain model; session filesystem не вважається довговічним сховищем.

**Резервний шлях:** якщо Runtime deployment не проходить timebox, зберегти справжній локальний Strands + Bedrock + live search і відтворювану інструкцію. Це RESCOPED, а не удаваний cloud PASS. Локальний fixture-only режим не зараховується як live discovery.

BDB контролює розробку й приймання, але не є runtime-залежністю QUALOR. Shared Product Bridge, Weekfield і Distribution Desk не підключаються в конкурсній версії.

## 08. Технічний стек і доступність

**Python 3.12** — baseline реалізації. Strands Agents SDK — автономна orchestration; Pydantic v2 — єдине джерело runtime domain schemas; FastAPI — локальний API; SQLite — локальна історія; HTTPX + обмежений HTML parser — отримання і розбір документів; pytest і Ruff — перевірки. Це наш вибір стеку, а не вимога використовувати всі ці бібліотеки від організатора.

**Frontend:** React, TypeScript, Vite, Tailwind v4; без UI framework migration та складної animation library. Node і package versions фіксуються в bootstrap після реальної installation/build перевірки. `uv.lock` і frontend lockfile входять у repo; неперевірених floating dependencies не залишається.

Pydantic схеми експортуються в JSON Schema/OpenAPI; TypeScript types генеруються з них. Browser-side validation може користуватися згенерованими схемами; дублювати правила eligibility в ручному TypeScript коді заборонено.

**Модель V1:** Claude Sonnet 4.6 через Bedrock — конкретний початковий кандидат, не твердження, що це найновіша чи найкраща доступна модель. S07 підтверджує модель та inference profiles. Для `us-east-1` перевіряємо `us.anthropic.claude-sonnet-4-6`; не припускаємо in-region доступність за одним лише model name. Інший model/profile потребує capability test і записаного рішення.

**Пошук:** AgentCore Web Search через Gateway/MCP. S05 підтверджує сервіс та стартову географію; доступність у нашому акаунті перевіряється окремо. Для V1 кандидат cloud region — `us-east-1`. US routing не називається EU-only residency. Публічне демо не містить приватних персональних даних.

Модель для написання коду через Codex — окрема development tool. Реалізація QUALOR не залежить від появи конкретної GPT-моделі, не використовує ChatGPT subscription як runtime API credential та не припускає існування не перевіреного Bedrock endpoint для неї.

## 09. Інструменти й межі автономії

Модель отримує тільки вузькі tools: `search_opportunities`, `fetch_official_page`, `extract_rule_candidates`, `compare_project`, `request_rule_evaluation`, `propose_decision`, `request_draft_pack`. Назви — контрактні наміри, не твердження про вже наявні функції SDK.

Кожен tool має typed input/output, власний timeout, бюджетну reservation і опис ефекту. Пошуковий query формується зі знеособлених потреб, а не повного founder profile. Перед web fetch код перевіряє hostname і схему. Ніякого довільного shell, install package, filesystem path або довільного MCP server з вебсторінки.

LLM може запропонувати новий source domain. У V1 автоматичне отримання повного документа дозволене лише в operator-approved source registry. Незнайомий домен зберігається як discovery candidate; допуск через профіль оператора, не через tool-call моделі. Ця межа звужує охоплення, але робить read-only prototype контрольованим.

LLM output валідується схемою, посиланнями та policy. Одна спроба schema repair дозволена в межах загального ліміту викликів; після повторної помилки — FAILED або PARTIAL з конкретною причиною, без підставляння вигаданого успіху.

Події trace містять виконану дію, тривалість, статус, evidence IDs і токени. В UI показуємо перевірювані reason codes та коротке пояснення, а не прихований chain-of-thought моделі.

## 10. Основні контракти даних

Усі записи мають `schema_version`, стабільний ID, UTC timestamps, джерело створення та версію. Monetary amounts зберігаються як decimal/minor units з currency; жодних floating-point грошей. Календарна дата без timezone не перетворюється на точний UTC момент мовчки.

**FounderProfile:** country of residence, legal form, incorporation data за наявності, team facts, availability hours, max cash commitment, constraints, verified_at. Кожне важливе поле має provenance: USER_ASSERTED, DOCUMENTED або UNKNOWN.

**ProjectProfile:** name, problem, audience, stage, available features, stack, code provenance, license intent, prior submissions, public-evidence references, estimated adaptation capacity. Немає автоматичного імпорту приватного коду.

**OpportunityRecord:** organizer, edition/cycle, canonical rules URL, application URL, tracks, deadlines, geographic scope, rewards, deliverables і source versions. Identity — organizer + normalized program + edition; tracking query parameters не створюють нового конкурсу.

**Reward:** CASH_PRIZE, CLOUD_CREDIT, GRANT, EQUITY_INVESTMENT або IN_KIND; amount/range, currency, eligibility, expiry, conditions, payment timing if known. Equity investment не відображається як безповоротний грант. Total prize pool не видається за суму, доступну одному переможцю.

**EvidenceRecord:** original URL, final URL, retrieval time, source type, content hash, короткий supporting excerpt, normalized field, extraction state. Hash підтверджує незмінність знімка, а не істинність тексту.

**RuleCandidate / RuleEvaluation:** rule type, operator, operand, criticality, evidence IDs, supported status, profile reference, PASS / FAIL / UNKNOWN / NOT_APPLICABLE, reason code, policy version. Модель не має права сама створити останній verdict поза rule engine.

**DecisionRecord:** opportunity version, profile/project versions, eligibility gate, conflict status, strategy score if available, effort range, recommendation, reasons, missing information, next action, freshness status.

**RunRecord / RunEvent:** mode LIVE / FIXTURE / REPLAY, run state, counters, budget reservations, actual reported usage, provider configuration, timestamps, events. **ApprovalRecord:** actor, scope, hashes/versions, expiry, one-time consumption. **DraftPack:** immutable output version, sources, missing fields, authoring facts і approval reference.

## 11. Evidence-first: що саме вважається підтвердженням

Пошуковий snippet — discovery hint, а не достатня підстава для hard eligibility. Правила й application documentation мають вищу вагу за marketing page. Датований офіційний amendment може змінити стару редакцію; невирішена суперечність дає REVIEW_REQUIRED, а не вибір зручнішого формулювання.

Кожен critical claim має supporting evidence: deadline, permitted entrant, geography, legal entity, new/existing work policy, license, required technology, financial-support restrictions та матеріальні умови вигоди. Якщо тип правила не застосовується, це потрібно обґрунтувати; порожнє поле не означає NOT_APPLICABLE.

Розділяємо structural verification та semantic correctness. Те, що уривок існує в документі й JSON валідний, ще не доводить правильного тлумачення. QUALOR відображає «підтверджено наведеним джерелом», а не «юридично гарантовано». На acceptance потрібна ручна звірка critical claims у gold corpus.

**Свіжість:** default policy — повторно перевірити critical rules не пізніше ніж через 24 години для actionable рішення; коли до deadline лишилося менше 72 годин — через 6 годин. Перед draft approval перевіряється freshness. Перевірка не продовжує actionability, якщо fetch не вдався: знімок залишається, але стає STALE.

Зберігати короткі уривки та metadata; повні сторінки — тільки приватно, за допустимого використання, з TTL. У public repo не комітяться повні чужі rules pages. Для fixtures переважно використовуються власні синтетичні тексти. Blocked pages, CAPTCHA, login walls та непідтримані PDF не обходяться; статус — REVIEW_REQUIRED із прямим посиланням.

## 12. Eligibility: детермінізм без хибної впевненості

Окреме правило має чотири стани: PASS, FAIL, UNKNOWN, NOT_APPLICABLE. Підсумковий gate має три: PASS, FAIL, REVIEW_REQUIRED. В UI PASS означає лише відповідність перевіреним умовам заданої policy version, а не остаточне рішення організатора.

**Агрегація:** будь-який підтверджений hard FAIL → FAIL. Немає FAIL, але є невідомий critical факт, незрозуміле правило, застарілі джерела або незавершений critical coverage checklist → REVIEW_REQUIRED. PASS можливий лише за повного required coverage, свіжих evidence та відсутності critical UNKNOWN. Порожній список правил не проходить перевірку.

Підтримувані V1 operators: equality, membership, numeric bounds, date interval, explicit boolean requirement; логічні AND/OR із збереженням UNKNOWN. Наприклад, PASS OR UNKNOWN може дати PASS тільки коли правило справді має альтернативні достатні умови. Модель не переписує AND на OR.

Особливі cases: residency не дорівнює citizenship; sole trader не автоматично incorporated company; «до семи років» перевіряється на вказану правилами дату; «новий проєкт» оцінюється за documented provenance; відсутність країни в короткому списку не доводить worldwide eligibility.

Невирішений legal або sponsor-support пункт — reason code для review. Не створюємо автоматичний юридичний verdict. Профільний override з поясненням зберігається окремо як рішення людини й не переписує джерело.

## 13. Відповідність, економіка та рекомендація

**Strategy score** — внутрішня пріоритизація, а не ймовірність виграшу. П'ять факторів оцінюються 0–4 за явно наведеною rubric: product fit (30%), readiness (25%), реалізовність у часовому вікні (20%), стратегічна користь (15%), економічна доступність (10%). Результат — ціле число 0–100 із розкладкою, без псевдоточних десяткових знаків.

0 означає відсутність придатного збігу або нереалістичну умову; 1 — слабкий match/велика невизначеність; 2 — часткову відповідність; 3 — сильну відповідність із невеликими gaps; 4 — прямий підтверджений match. Конкретні оцінки прив'язуються до project facts і доступного часу. Відсутній факт не підміняється середнім балом: aggregate score приховується, поки фактори не оцінено.

Вага — стартова product hypothesis. До її зміни потрібні зафіксовані dogfood результати й нова policy version. Коректний детермінований підрахунок не робить вихідні subjective ratings об'єктивною статистикою.

**Recommendation policy V1, за порядком пріоритету:** closed/expired, hard FAIL або explicit conflict → SKIP; REVIEW_REQUIRED, невирішений conflict або невідомий score → WATCH; PASS, score ≥75, підтверджені capacity/витрати та materials ready → APPLY; PASS, score ≥60, виконувані gaps і доступна capacity → PREPARE; PASS, score ≥60, але capacity/витрат бракує або вони невідомі → WATCH; інакше SKIP. Непідтверджене поле ready забороняє APPLY. Жоден нижчий пункт не скасовує вищий.

Effort показуємо діапазоном і task breakdown: integration, evidence, repo/license cleanup, demo, narrative, submission. Це оцінка підготовки конкретної заявки, не час виконання агента. Різні валюти, готівка, credits і equity не зводяться до однієї суми без пояснення. Очікувану грошову вартість не рахуємо без обґрунтованої ймовірності.

## 14. Конфлікти й походження роботи

QUALOR аналізує лише явно введені ActiveSubmission records: contest, project lineage, code origin, sponsor support, dates, license та disclosed reused components. Він не стверджує, що перевірив усі зовнішні договори або всі конкурси користувача.

Статуси: BLOCKED_BY_EXPLICIT_RULE, REVIEW_REQUIRED, NO_CONFLICT_DETECTED_IN_CHECKED_RULES. Останній не скорочується до юридично абсолютного «конфліктів немає». Відсутні правила іншої програми дають неповне coverage.

Для нашої розробки QUALOR — новий repo та власна реалізація. Дозволені інструменти, бібліотеки й знання не плутаються з правом копіювати proprietary код інших продуктів. Стандартні компоненти фіксуються у provenance record із ліцензіями. Відкриття будь-якого коду потребує rights review.

Наявність одного AWS-акаунта сама по собі не вирішує питання sponsor support. Tag розмежовує ресурси, але не доводить, який credit юридично фінансував проєкт. Походження $200, умови можливих $50/$1,000 та відповідність конкретним правилам — окремий operator checklist. Не чекати $1,000 для локальної розробки; неоднозначність credits/support закрити письмовим clarification до конкурсного подання. Сам цей пакет не містить такого дозволу.

## 15. Стан, повторні запуски та людське погодження

Run states: CREATED → RUNNING → COMPLETED / PARTIAL / FAILED / CANCELLED / BUDGET_STOPPED. Decision state не дорівнює run state: PARTIAL run може містити окремі повністю перевірені записи, але UI зобов'язаний показати неповне охоплення.

Approval не тримає cloud session відкритою. Run завершується; readiness brief і approval request зберігаються. Після дії людини запускається новий bounded drafting job. Scope V1 — тільки `GENERATE_DRAFT_PACK`, без зовнішньої submission.

Approval прив'язано до actor, opportunity hash, profile/project versions, policy version, action і expiry; default expiry — 24 години або deadline, залежно від того, що раніше. Зміна critical rules, профілю чи ліцензії анулює попередній approval. Approval є одноразовим; повторний network retry повертає той самий результат за idempotency key.

Dedup: semantic digest містить нормалізовані critical fields та edition, але не весь HTML. Зміна рекламного банера не створює alert. Незмінені записи не дублюються. STALE evidence не видається за нову перевірку після невдалого fetch.

Локальні записи проходять SQLite transactions. Cloud adapter застосовує версії/conditional writes й один активний lease; конкурентний start повертає BUSY, а не запускає другого агента. Append-only event history і hashes підтримують аудит, але V1 не заявляє криптографічну незаперечність або WORM-архів.

## 16. Безпека, приватність і захист бюджету

Усі зовнішні сторінки — недовірені дані. Текст «ignore previous instructions», приховані tool calls або пропозиція надіслати profile на інший сайт не може надати прав. Немає secret-bearing інструментів у model toolset; credentials залишаються в SDK/IAM контурі.

Web fetch дозволяє HTTPS, обмежений список доменів і контрольовані redirects. Блокуються loopback, private/link-local addresses, cloud metadata endpoints, non-HTTP schemes, credential URLs і DNS rebinding. Перевірка повторюється після redirect; DNS/IP прив'язка не повинна залишати check/use gap. Response size, timeout і content type мають жорсткі межі. Якщо безпечний transport не реалізовано, функція fetch не проходить release gate.

Локальний API binds to 127.0.0.1, має обмежений origin і захист state-changing endpoints. Публічний demo — read-only sanitized snapshot/replay. Ніякого public anonymous endpoint, здатного запускати оплачувані LLM/search calls. Owner live execution — через локальний контролер і AWS short-lived credentials; окрема full SaaS auth система не потрібна.

Secrets не передаються в browser, prompts, git, screenshots чи video. Cloud IAM role scoped до QUALOR resources і model/inference profile; немає `AdministratorAccess`. AWS API calls і outward network access — різні межі; IAM не замінює SSRF policy.

**Default limits одного run:** один активний run; до 20 discovery candidates; глибока перевірка до 5; до 6 search queries, 12 fetches і 16 model invocations включно з retries/repair; до 75,000 input і 12,000 output tokens сумарно; wall timeout 300 секунд; application estimate ceiling $0.75. Якщо counters або cost rate невідомі, новий платний виклик заборонений.

Перед кожним платним викликом резервується консервативна верхня вартість; після відповіді звіряється reported usage. Interrupted call не обнуляє reservation до reconciliation. Модель не може змінити ці межі. Виклики SDK, retries та parallel tool calls не можуть обійти guard. Ліміти треба довести fault-injection тестами.

## 17. Інтерфейс і продуктова якість

UI — робоча поверхня для рішень, а не chat-first екран. Desktop composition: вузька навігація; центральна черга; evidence/decision drawer праворуч. Основні розділи — Inbox, Portfolio, Runs; Settings лише для потрібних конфігурацій.

Картка показує program/edition, відповідний проєкт, recommendation, eligibility scope, reward type, deadline із timezone, effort range, найважливіший blocker і freshness. Strategy score має tooltip «пріоритет, не шанс перемоги»; за недостатніх даних замість числа — Not enough evidence.

Evidence drawer показує claim → уривок → source URL → retrieved_at → source version. Run timeline показує реальні події. Не можна відтворювати анімований фальшивий live progress із заздалегідь заготовленими числами.

Візуальний напрям: стриманий аналітичний інструмент; графітова або світла нейтральна база, виразна типографіка, один accent, без декоративного sci-fi шуму. Спочатку читабельність і contrast, потім motion. Status має текстову мітку й іконку, а не лише колір.

Required states: empty profile, no results, partial source failure, stale evidence, unknown eligibility, budget stopped, disconnected live provider, pending approval, revoked approval і finished pack. Keyboard navigation, visible focus, reduced motion, readable 320–1440 px layout — базовий QA. Конкурсна UI і materials — англійською; канонічна документація для власника — українською. Повна i18n не входить у MVP.

## 18. Вимірювання та acceptance

Перевірки поділено на deterministic domain tests, contract tests, adapter tests, adversarial/security tests, browser end-to-end і маленький live evaluation set. Повний перелік case IDs наведено в `02_REQUIREMENTS_AND_EVALUATION.md`.

**Safety invariants:** жоден тестовий confirmed FAIL або critical UNKNOWN не стає APPLY; чужий excerpt не вважається доказом потрібного claim; неможливе зовнішнє подання; approval не переживає critical version change; budget guard охоплює retry; prompt injection не розширює capabilities.

**Якісні цілі, не поточні результати:** 100% проходження critical deterministic suite; не менш ніж 90% exact-field accuracy на мінімум 30 вручну розмічених critical claims; нуль небезпечних false-PASS у цьому наборі. Розмір вибірки та помилки завжди публікуються поруч; це не статистична гарантія роботи на всьому web.

Live gate: щонайменше 5 зафіксованих bounded runs на датованому source set; не менш як 4 доходять до валідного кінцевого результату, а решта чесно показує PARTIAL/FAILED. Кожен promoted APPLY переглядається вручну. Latency і cost фіксуються фактичними значеннями; оптимізація проводиться після correctness.

Dogfood outcome: для 10 вручну переглянутих можливостей зафіксувати прийняті/відхилені рекомендації, виправлення, невідомі умови й час людини. Економію часу вимірюємо against recorded manual baseline; не пишемо «економить 10 годин на тиждень» без вимірювання.

## 19. Бюджет і операційна модель

Strands library, модель, search, Runtime, storage та logs — різні позиції. Наявний credit balance не є бюджетом, який треба витратити. Облік QUALOR ведеться за gross service usage до credits, а також окремо за можливим cash exposure.

Плановий розподіл максимуму $40: $20 inference; $5 search/Gateway; $5 Runtime/storage/logs; $10 safety/availability reserve. Це allocation, не тариф і не прогноз фактичного рахунку. По $10 / $20 / $30 — контрольні повідомлення; на внутрішньому ledger $30 нові live runs блокуються до review, залишаючи резерв.

За S06 Web Search коштує $7 за 1,000 queries: шість queries — $0.042 без Gateway/model/Runtime. Для inference не фіксуємо ціну з чужої платформи: перед paid smoke заповнюється перевірена rate card для обраного Bedrock profile, region і режиму. Model cost = input tokens × input rate + output tokens × output rate; cache/reasoning charges враховуються лише за підтвердженим тарифом.

**Критичне виправлення:** AWS Budgets має затримку billing data і не є миттєвим hard cap [S08]. Наш runtime guard обмежує керовані виклики, але не всі можливі рахунки акаунта. Storage, logs, transfers або вже запущені ресурси можуть продовжити накопичення витрат. Потрібні короткий retention, teardown plan, перевірка ресурсів і запас.

Не створюємо NAT Gateway, RDS, OpenSearch, provisioned throughput чи постійні browser sessions. Cloud resources мають `Project=QUALOR`, `Environment=hackathon`, `Owner=BrenychStudio`; billing tags треба активувати й перевірити, а не вважати автоматично доступними. Project tags не завжди достатні для атрибуції shared Bedrock charges, тому потрібен application usage ledger.

Публічна сторінка показує read-only replay без inference. Платний live-доступ під час judging вмикається лише контрольовано; витрати після submission не забуваються. Cleanup не повинен знищити збережені матеріали для суддів.

## 20. Roadmap: чотири спринти, одна вертикаль

**Sprint 1 / QUALOR-00–02 / до 12 годин.** Чистий bootstrap, зафіксовані залежності, domain contracts, synthetic fixtures, eligibility/decision tests, один Strands agent. На початку — короткий probe model/search доступу, щоб не відкласти інтеграційний ризик на кінець. Гейт: від профілю до відтворюваного рішення з evidence і guard; FIXTURE чітко відокремлено від LIVE.

**Sprint 2 / QUALOR-03–04A / до 12 годин.** Реальний discovery/fetch, AWS integration, persistence, minimum inbox, one-time approval і draft pack. Гейт: live source → evidence → decision → approved local pack; trace, cost, restart, stale approval test. AgentCore Runtime — ціль deployment, а не привід переписати продукт.

**KILL / RESCOPE GATE після Sprint 2.** Якщо немає справжнього end-to-end сценарію, потрібно обирати: скоротити provider/hosting scope без фальсифікації можливостей або припинити конкурсну розробку. Не переносити термін і не додавати третій інфраструктурний спринт автоматично. До цього моменту витрачено не більш як 24 години сфокусованої роботи.

**Sprint 3 / QUALOR-04B–05 / до 8 годин.** UX polish, зміни між runs, security/evaluation suite, малий dogfood, відтворення в чистому середовищі. Гейт: acceptance cases і чесний evidence report. Feature freeze після цього етапу.

**Sprint 4 / QUALOR-06 / до 8 годин.** README, code/license review, architecture diagram, демонстраційне відео, Devpost fields, submission validation; blog content тільки з реальної роботи та за залишком часу. Гейт: release tag/commit, перевірені links, submission receipt і owner approval публікації.

Точні дати execution визначаються за фактичним проходженням гейтів до внутрішнього target. Календар не перетворює FAIL на PASS. Після 12 вересня 18:00 Europe/Madrid нові features не починаються; залишаються виправлення критичних дефектів і submission.

## 21. Ведення розробки та контроль змін

Кожен task отримує ID, goal, dependencies, baseline commit, file plan, acceptance tests, budget impact і explicit out-of-scope. Codex виконує маленькі перевірювані зміни; конкретні implementation tasks готуються після приймання цього baseline, а не змішуються з ним.

Result packet має містити HEAD_BEFORE/AFTER, branch, changed files, executed commands, exit codes, test counts, live-vs-fixture status, витрати/usage, unresolved issues, artifact paths, push/deploy status. `STATUS=PASS` дозволений тільки для scope, реально перевіреного тестами. Development code не вважається конкурсно готовим лише після build.

Нові функції проходять Change Request: проблема, очікувана користь, зміна часу/бюджету, які вимоги витісняються, рішення власника. За замовчуванням change після Sprint 2 відхиляється або переходить у post-competition backlog.

Git policy: окремий repo, scoped branch per task, clean baseline check, жодних mass replacements або переносів приватних кодових баз; commit з тестами; push/public visibility/deployment тільки за окремим дозволом. BDB workspace реєструється через штатний локальний процес; цей пакет не реєстрував його та не staged execution manifest.

## 22. Конкурсний пакет і демонстрація

Пакет має довести проблему, автономну дію, результат, безпеку й відтворюваність. Публічна частина не містить приватного founder profile, AWS account IDs, credential values, client data чи повних чужих rules texts. Перед публікацією — secrets/dependency/license scan і manual rights review.

**Ліцензія:** MIT — рекомендований baseline для окремої конкурсної реалізації; остаточне відкриття коду та перевірка third-party dependencies належать власнику. Володіння авторськими правами не скасовує наданих open-source дозволів. Не планувати майбутню комерційну модель на припущенні, що відкритий код можна «забрати назад».

Сценарій відео: проблема засновника → короткий профіль → справжній live scan → обґрунтована відмова за hard rule → невідомість, яку агент не приховав → сильний match → approval → готовий draft pack → зміна правила та invalidation. У п'ятихвилинний формат потрапляють лише реально реалізовані фрагменти.

Часозатратні частини можна скоротити монтажем, чітко позначивши time compression. Replay, fixture та live мають видимі мітки. Synthetic opportunities не видаються за чинні програми. Architecture diagram відображає deployment факту, а не wish list.

Текст submission пояснює, чому агент не просто чат: він сам обирає перевірки, використовує live tools, створює артефакт і запитує людину лише на визначеній межі. Technical articles пишуться з реальних decisions, cost results і failures; бонус не є приводом публікувати порожній marketing content.

## 23. Після конкурсу: умовне продовження

Результат конкурсу й продуктова цінність оцінюються окремо. Нагорода не гарантує ринок, а відсутність нагороди не означає відсутності користі. Подальша розробка дозволяється лише після dogfood і відгуків реальних користувачів.

Перший post-competition крок — кілька засновників/студій з consented profiles, виміряні accepted recommendations, кількість помилок і час ручної перевірки. Ознака цінності — люди повертаються до inbox і використовують підготовлені пакети, а не лише хвалять візуальне оформлення.

Можлива еволюція: schedule + notification adapter; більше official sources; calibrated rubric; контрольований multi-user доступ; далі — комерційна підписка або paid workflow. Жодні ціни, строки SaaS launch чи майбутня виручка не затверджуються цим брифом.

Clients, tenders, partnerships і procurement — окремі майбутні домени з іншими rules. Їх не додаємо через «це майже те саме». Необхідна окрема перевірка приватності, умов джерел, економіки та продуктового фокусу.

## 24. Остаточні інваріанти й поточний стан

QUALOR має бути корисним без виграшу; достатньо вузьким для нашого ліміту; чесним щодо доказів; безпечним щодо прав і бюджету; незалежним від proprietary систем Brenych Studio; відтворюваним за документацією.

**Ніколи:** вигадувати opportunity або deadline; рахувати credits як cash; видавати strategy score за шанс; перетворювати UNKNOWN на PASS; називати mock live; автоматично подавати заяву; вважати AWS Budget hard cap; робити доступ до API публічно необмеженим; змінювати owner constraints без CR.

**Поточна точка:** FOUNDATION_PREPARED. NAME=APPROVED; ARCHITECTURE_A=APPROVED; DETAILED_BASELINE=REVIEW_READY; REPO_BOOTSTRAP=NOT_STARTED; CLOUD_ACCESS=NOT_TESTED; CREDIT_COVERAGE=NOT_VERIFIED; LIVE_AGENT=NOT_IMPLEMENTED; SUBMISSION=NOT_PREPARED. Це документаційний checkpoint, не execution PASS.

Наступний дозволений крок після review baseline — QUALOR-00: контрольований bootstrap та capability preflight за окремим task. Реєстрація у конкурсі, запит кредитів, repo publication і витрати перевіряються власником окремо. Жоден із цих фактів не вважається виконаним лише через існування цього пакета.

## 25. Джерела та межі перевірки

Джерела перевірено 05.09.2026. Тут наведені лише короткі опорні факти; точний актуальний текст має перевагу над переказом. Доступність продукту в документації не доводить доступність у нашому акаунті. Повний реєстр і задачі повторної перевірки — `05_VERIFIED_SOURCES.md`.

**S01 — Official Rules, Agents for Humans.** Вхід відкритий фізичним особам; submission period 10.08–14.09.2026, 17:00 Pacific. Потрібна нова робота; є disclosure та sponsor-support умови. Одна робота може отримати один приз. Джерело: https://agentsforhumans.devpost.com/rules

**S02 — Competition overview.** Strands обов'язковий; AgentCore optional. Пакет: public repo з MIT/Apache, README, architecture diagram, video до 5 хвилин, Builder ID; English materials. Джерело: https://agentsforhumans.devpost.com/

**S03 — FAQ.** Запит $50 credits — до 11.09.2026, 12:00 Pacific, для зареєстрованих учасників, за наявності. Джерело: https://agentsforhumans.devpost.com/details/faqs

**S04 — Strands structured output.** Python structured output використовує Pydantic; schema validation не гарантує істинність змісту. Джерело: https://strandsagents.com/docs/user-guide/concepts/agents/structured-output/

**S05 — AWS Web Search announcement, 16.06.2026.** Gateway/MCP connector; у повідомленні доступність US East (N. Virginia). Джерело: https://aws.amazon.com/about-aws/whats-new/2026/06/amazon-bedrock-agentcore-web-search/

**S06 — AgentCore pricing.** Web Search $7/1,000 queries; модель, Runtime, Gateway, storage і logs мають окремі складові. Джерело: https://aws.amazon.com/bedrock/agentcore/pricing/

**S07 — Bedrock Sonnet 4.6 model card.** Підтверджує model та geo inference identifiers; регіональні режими відрізняються. Джерело: https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-sonnet-4-6.html

**S08 — AWS Budgets.** Оновлення й сповіщення затримуються; рахунок може перевищити notification threshold. Джерело: https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html

**S09 — Promotional credit terms.** Покриття обмежене eligible services та умовами конкретного credit. Джерело: https://aws.amazon.com/awscredits/

**S10 — Applying AWS credits.** AWS застосовує credits за власними billing rules; tags не задають довільний вибір credit. Джерело: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/useconsolidatedbilling-credits.html

**S11 — AgentCore Runtime.** Документація hosting/runtime; production persistence та API integration потребують окремого smoke test. Джерело: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html

**S12 — Strands Bedrock provider.** Референс провайдера й налаштувань; встановлену версію перевіряти в bootstrap. Джерело: https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/
