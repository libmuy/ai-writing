可以像下面這樣順序生成小説嗎：
1. 生成多個故事概要（以用戶輸入的想法爲輸入）
2. 用戶選擇其中一個
3. 以用戶選擇的故事，生成多個世界設定
4. 用戶選擇其中一個，并可以輸入想法進行調整
5. 生成 constitution.md 和 world.yaml 和 novel_plan.json

AI model should can be configurated, for example use openai or deepseek, etc.
lets add a configuration file to config the AI model providers.
what model the agents use should can be configurated too.



commands:

trate current directory as the novel work directory.

- `init`:
  - Creates folder structure and starter files.
  - Must be safe to re-run.
  - Must not overwrite existing user content unless `--force` is provided.
- `status`:
  - show status: initted? setup done(world generated)? chapter2 generated?
- `setup`: setup world
  1. User provides idea.
  2. Generate synopsis candidates.
  3. User selects or asks to regenerate with feedback.
  4. Generate world candidates.
  5. User selects or asks to regenerate with feedback.
  6. Setup Writer emits `constitution.md`, `world.yaml`, and `novel_plan.json`.
- `setup constitution [user ieda text]`: regenerate constitution.md
- `setup world [user ieda text]`: regenerate world.yaml
- `setup plan [user ieda text]`: regenerate novel_plan.md
- `generate [charapter range]`:
  - generate chapter[s]
  - Allowed only when setup is already complete.
  - If setup is missing, command should fail with a clear message.

I am considering to add a simple Arc Manager(framework) to phase1
and remove generation of novel_plan.json from setup command.
and add a new command:
- `plan novel`: generate `novel_plan.json`
- `plan arc [arc range]`: generate the arc plan file
- `plan chapter [chapter range]`: generate `novel_plan.json`

what do you think?


