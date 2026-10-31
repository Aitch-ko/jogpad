# Changelog

## [0.9.0](https://github.com/Aitch-ko/jogpad/compare/v0.8.0...v0.9.0) (2026-10-31)


### Features

* a programmed CH57x pad works without key setup, a knob per axis ([#48](https://github.com/Aitch-ko/jogpad/issues/48)) ([29649c8](https://github.com/Aitch-ko/jogpad/commit/29649c8d5137b30051572e713bde963daf2d57f0))
* the web page has a light/dark switch ([#50](https://github.com/Aitch-ko/jogpad/issues/50)) ([58f200a](https://github.com/Aitch-ko/jogpad/commit/58f200aff5c08ac5156aec7f95fdc3aef166e8ac))
* the web page shows axes, STOP and the step size in colour ([#49](https://github.com/Aitch-ko/jogpad/issues/49)) ([3dd1009](https://github.com/Aitch-ko/jogpad/commit/3dd1009f4fda5528e2d37cfbe03aa900095d1395))

## [0.8.0](https://github.com/Aitch-ko/jogpad/compare/v0.7.1...v0.8.0) (2026-10-31)


### Features

* jogpad program-pad writes the layout's key codes into a CH57x pad ([#47](https://github.com/Aitch-ko/jogpad/issues/47)) ([4a8c00e](https://github.com/Aitch-ko/jogpad/commit/4a8c00e01f5ae338a1957c5aac500c4fa640a355))


### Bug Fixes

* the CH57x drawing shows the knobs where the real pad has them ([#45](https://github.com/Aitch-ko/jogpad/issues/45)) ([d7a84d0](https://github.com/Aitch-ko/jogpad/commit/d7a84d0107e795ff18a0b526408c8041ccdb9812))

## [0.7.1](https://github.com/Aitch-ko/jogpad/compare/v0.7.0...v0.7.1) (2026-10-25)


### Bug Fixes

* a lock on an object the firmware does not know refuses moves ([#41](https://github.com/Aitch-ko/jogpad/issues/41)) ([339efe1](https://github.com/Aitch-ko/jogpad/commit/339efe114bb7970a008955005dfa670b88b73d49))

## [0.7.0](https://github.com/Aitch-ko/jogpad/compare/v0.6.1...v0.7.0) (2026-10-25)


### Features

* installer builds jogpad's venv from JOGPAD_PYTHON, with a way out of Python 3.9 ([#39](https://github.com/Aitch-ko/jogpad/issues/39)) ([49bd37c](https://github.com/Aitch-ko/jogpad/commit/49bd37c34f72e8623d5196a25842072d22108264))


### Documentation

* one note on Claude Code instead of a trailer in every commit ([#38](https://github.com/Aitch-ko/jogpad/issues/38)) ([3158e41](https://github.com/Aitch-ko/jogpad/commit/3158e41062e3baf1f27cc648acb55fea4b72bf0e))

## [0.6.1](https://github.com/Aitch-ko/jogpad/compare/v0.6.0...v0.6.1) (2026-10-25)


### Documentation

* installer names the web page, installation guide says what to do there ([#35](https://github.com/Aitch-ko/jogpad/issues/35)) ([25bfa23](https://github.com/Aitch-ko/jogpad/commit/25bfa239657681bf159e3afadad296ec0c4e1033))

## [0.6.0](https://github.com/Aitch-ko/jogpad/compare/v0.5.0...v0.6.0) (2026-10-25)


### Features

* installer and jogpad setup-switch add the switch to Klipper and Moonraker ([#33](https://github.com/Aitch-ko/jogpad/issues/33)) ([eaf72e4](https://github.com/Aitch-ko/jogpad/commit/eaf72e434b736a264c7c77a903ebb4a0f74842a7))

## [0.5.0](https://github.com/Aitch-ko/jogpad/compare/v0.4.0...v0.5.0) (2026-10-25)


### Features

* setup section of the web page starts folded away ([#29](https://github.com/Aitch-ko/jogpad/issues/29)) ([f4cce37](https://github.com/Aitch-ko/jogpad/commit/f4cce3744a2f7d5b947e72c489a270e2b39b5364))
* show the pad as a camera panel in Mainsail and Fluidd ([#30](https://github.com/Aitch-ko/jogpad/issues/30)) ([2c4f3fc](https://github.com/Aitch-ko/jogpad/commit/2c4f3fc129b7c01b73a60795106b0ec6b17ab300))
* switch jogpad on and off from its page and camera panel ([#32](https://github.com/Aitch-ko/jogpad/issues/32)) ([bdc67cb](https://github.com/Aitch-ko/jogpad/commit/bdc67cba6a953bddb91f10ed6f49f0ad1a0c5bac))
* switch jogpad on and off in Mainsail and Fluidd ([#28](https://github.com/Aitch-ko/jogpad/issues/28)) ([ee6f8ac](https://github.com/Aitch-ko/jogpad/commit/ee6f8acb2e2427dd6dc574469354fe5904dfa290))


### Bug Fixes

* keep web page requests out of the journal ([#27](https://github.com/Aitch-ko/jogpad/issues/27)) ([ac58baf](https://github.com/Aitch-ko/jogpad/commit/ac58bafa53bfb89e953f51e7376c5422d5522d91))


### Documentation

* usage.md switch section, API reference, panel screenshot. ([bdc67cb](https://github.com/Aitch-ko/jogpad/commit/bdc67cba6a953bddb91f10ed6f49f0ad1a0c5bac))

## [0.4.0](https://github.com/Aitch-ko/jogpad/compare/v0.3.0...v0.4.0) (2026-10-25)


### Features

* web page open in the network, changes only from computers Moonraker trusts ([#25](https://github.com/Aitch-ko/jogpad/issues/25)) ([29fb062](https://github.com/Aitch-ko/jogpad/commit/29fb062703fa313c0e5b1faa8b72d2d9d4407bc2))


### Bug Fixes

* start message reaches the journal right away ([#26](https://github.com/Aitch-ko/jogpad/issues/26)) ([6a57431](https://github.com/Aitch-ko/jogpad/commit/6a574318704731aaf7f63bd2d4a2b0ca0feff73f))


### Documentation

* getting started, documentation map and repository layout in the README ([#23](https://github.com/Aitch-ko/jogpad/issues/23)) ([47ba03a](https://github.com/Aitch-ko/jogpad/commit/47ba03a5c1e615ceca77c4b13e43a26d15b966c9))

## [0.3.0](https://github.com/Aitch-ko/jogpad/compare/v0.2.0...v0.3.0) (2026-10-24)


### Features

* page header and footer, language menu, design tokens with checked contrast ([#17](https://github.com/Aitch-ko/jogpad/issues/17)) ([4ad5871](https://github.com/Aitch-ko/jogpad/commit/4ad5871c1f26b1496ab59fab2604d071d5313c0a))
* planned key codes for the CH57x macro pad layout ([#22](https://github.com/Aitch-ko/jogpad/issues/22)) ([f8468b3](https://github.com/Aitch-ko/jogpad/commit/f8468b3caa8d380a9ce8e32e0680399eb068cce1))


### Documentation

* an animation at the top of the README showing what jogpad does ([#21](https://github.com/Aitch-ko/jogpad/issues/21)) ([5f42cfb](https://github.com/Aitch-ko/jogpad/commit/5f42cfb9af0376602ea5f858fcaa9e6b187eaac0))
* screenshots of the web page, made by a script ([#20](https://github.com/Aitch-ko/jogpad/issues/20)) ([8a2747f](https://github.com/Aitch-ko/jogpad/commit/8a2747f5be78920750dcee00dfcbd185c9a373c7))

## [0.2.0](https://github.com/Aitch-ko/jogpad/compare/v0.1.0...v0.2.0) (2026-10-24)


### Features

* add an installer that sets jogpad up as a service ([#11](https://github.com/Aitch-ko/jogpad/issues/11)) ([2cc2609](https://github.com/Aitch-ko/jogpad/commit/2cc260913b1c76331276e6efac323caf69654d98))
* announce moves and homing in the console ([#9](https://github.com/Aitch-ko/jogpad/issues/9)) ([8872abd](https://github.com/Aitch-ko/jogpad/commit/8872abd501c1c3d5ea70660e99cfece691e45774))
* learn keys and check axis directions on the web page ([#15](https://github.com/Aitch-ko/jogpad/issues/15)) ([3e74c14](https://github.com/Aitch-ko/jogpad/commit/3e74c1402a18de5715e493cefb44986964d0c760))
* web page with the pad drawn and live key presses ([#14](https://github.com/Aitch-ko/jogpad/issues/14)) ([0858933](https://github.com/Aitch-ko/jogpad/commit/0858933ef1b6a996c4d30824981e51da542dc7dd))


### Bug Fixes

* show installer progress and ask for sudo up front ([#12](https://github.com/Aitch-ko/jogpad/issues/12)) ([fc4cc85](https://github.com/Aitch-ko/jogpad/commit/fc4cc85c50881ef2e33360f76407e5c6d23e8c11))


### Documentation

* tell why jogpad exists, add a logo and use cases ([#16](https://github.com/Aitch-ko/jogpad/issues/16)) ([8de7e50](https://github.com/Aitch-ko/jogpad/commit/8de7e50f7d83d3e9b41a7a5378342817798247ef))

## 0.1.0 (2026-10-24)


### Features

* jog Klipper from a keypad or macro pad ([#7](https://github.com/Aitch-ko/jogpad/issues/7)) ([699fcc3](https://github.com/Aitch-ko/jogpad/commit/699fcc316a54b493919987b4d9336f5060af10eb))
