# Architecture

## Общий подход

NoteKeeper строится вокруг гексагональной архитектуры с чистым доменным ядром.

Цель архитектуры - отделить бизнес-логику приложения от внешних инструментов и интерфейсов: WhisperX, SpeechBrain, DeepSeek API, SQLite, файловой системы, CLI, Web API и Web UI.

Внутренние слои не должны зависеть от внешних реализаций. Внешние инструменты подключаются через порты и адаптеры.

## Слои приложения

```text
domain
  models
  services
  value_objects
  errors

application
  use_cases
  ports
  commands
  results

infrastructure
  sqlite
  filesystem
  ffmpeg
  whisperx
  speechbrain
  deepseek
  tokenization

interfaces
  cli
  api

jobs
  runner
  worker

composition
```

## Domain

Domain - внутренний слой приложения. Он содержит бизнес-сущности и бизнес-правила, которые не зависят от внешних библиотек, базы данных, API или пользовательских интерфейсов.

### Models

Ключевые доменные модели:

- `Campaign`
- `Participant`
- `AudioTrack`
- `VoiceSample`
- `AudioMetadata`
- `Transcript`
- `TranscriptSegment`
- `Recap`
- `ProcessingJob`
- `SpeakerLabel`
- `SpeakerMapping`
- `TimeRange`

### AudioMetadata

`AudioMetadata` - value object для технических свойств аудиофайла.

Он хранит технические данные без бизнес-смысла:

- duration;
- sample rate;
- channels;
- codec;
- format;
- bitrate;
- file size;
- checksum;
- другие технические параметры, полученные при probing аудио.

`AudioTrack` и `VoiceSample` содержат `AudioMetadata` как поле.

`AudioTrack` отвечает за бизнес-смысл записи игровой сессии: campaign, участники, связь с транскриптом, рекапом и джобами.

`VoiceSample` отвечает за бизнес-смысл голосового образца: campaign, участник, связь с embedding и speaker identification.

### SpeakerLabel

`SpeakerLabel` описывает label говорящего в transcript или diarization output.

Label может быть:

- anonymous: технический label вроде `SPEAKER_00`;
- named: пользовательский label вроде имени участника.

### SpeakerMapping

`SpeakerMapping` описывает решение о сопоставлении анонимного speaker label с конкретным участником campaign.

Он может хранить:

- anonymous label;
- named label;
- participant id;
- confidence;
- source: automatic, manual, sample-based, embedding-based;
- status: confirmed, uncertain, rejected.

### TimeRange

`TimeRange` описывает временной интервал внутри аудио или транскрипта.

Он используется в transcript segments, words, speech turns, speaker intervals, recap chunks и предупреждениях pipeline.

## Domain Services

Domain services содержат бизнес-логику, которая работает только с доменными моделями и value objects.

Примеры:

- правила добавления participant в campaign;
- правила добавления voice sample;
- проверка готовности campaign к обработке записи;
- правила применения `SpeakerMapping` к transcript;
- определение неопределенных или конфликтных speaker mappings;
- merge аудиодорожек на уровне доменных моделей;
- базовая валидация transcript segments и time ranges.

Domain services не должны ссылаться на WhisperX, SpeechBrain, DeepSeek, SQLite, FastAPI, Typer или файловую систему.

## Application

Application layer оркестрирует пользовательские сценарии через use cases.

Он знает порядок выполнения операций, но обращается к внешнему миру только через ports.

Примеры use cases:

- `CreateCampaign`
- `AddParticipantToCampaign`
- `AddVoiceSample`
- `CreateSpeakerEmbedding`
- `SubmitRecordingForProcessing`
- `RunTranscriptionJob`
- `ReviewSpeakerMappings`
- `GenerateRecap`
- `ExportTranscriptMarkdown`
- `ExportRecapMarkdown`
- `GetJobStatus`

Application layer может использовать доменные модели и сервисы, но не должен напрямую зависеть от конкретных реализаций инфраструктуры.

## Ports

Ports описывают интерфейсы, которые нужны application layer для работы с внешним миром.

Примеры портов:

- `CampaignRepository`
- `ParticipantRepository`
- `AudioTrackRepository`
- `VoiceSampleRepository`
- `TranscriptRepository`
- `RecapRepository`
- `JobRepository`
- `ArtifactStorage`
- `AudioProcessor`
- `Transcriber`
- `Aligner`
- `Diarizer`
- `SpeakerEmbedder`
- `SpeakerIdentifier`
- `RecapGenerator`
- `Tokenizer`
- `Clock`
- `IdGenerator`

Порты определяют, что нужно приложению, но не определяют, какой конкретной библиотекой это будет реализовано.

## Infrastructure

Infrastructure содержит реальные адаптеры к внешним системам и библиотекам.

Примеры:

- `SQLiteCampaignRepository`
- `SQLiteJobRepository`
- `LocalArtifactStorage`
- `FfmpegAudioProcessor`
- `WhisperXTranscriber`
- `WhisperXAligner`
- `SpeechBrainSpeakerEmbedder`
- `SpeechBrainSpeakerIdentifier`
- `DeepSeekRecapGenerator`
- `TokenCounter`

В этом слое допустимы зависимости от конкретных библиотек, subprocess, API clients, путей к файлам, GPU/CPU настроек и внешних сервисов.

## Interfaces

Interfaces - входные адаптеры приложения.

На ранних стадиях основным интерфейсом является CLI на Typer.

На третьей стадии добавляются:

- FastAPI Web API;
- React Web UI.

CLI и API не должны содержать бизнес-логику. Они принимают входные данные, вызывают application use cases и возвращают результат пользователю.

## Jobs

Jobs layer отвечает за выполнение длительных задач.

Транскрипция и генерация рекапа для записи на 3-5 часов являются долгими операциями, поэтому они должны быть представлены как jobs.

На ранней стадии job runner может быть синхронным. Позже его можно заменить на очередь и отдельный worker без изменения доменного ядра и use cases.

## Composition

`composition` - центральная входная точка в приложение.

Этот слой отвечает за:

- сборку приложения;
- создание application use cases;
- подключение реальных инфраструктурных адаптеров;
- передачу зависимостей через ports;
- чтение и применение настроек приложения;
- выбор runtime-режима: CLI, API, worker;
- настройку путей к SQLite, файловому хранилищу и временным директориям;
- подключение DeepSeek API key;
- выбор CPU/GPU режима;
- настройку WhisperX, SpeechBrain и ffmpeg;
- настройку thresholds, chunk sizes и других параметров pipeline.

Именно `composition` знает, какие конкретные реализации используются в текущем запуске приложения.

Остальные слои не должны самостоятельно создавать инфраструктурные зависимости.

## Основное правило зависимостей

Зависимости направлены внутрь:

```text
interfaces -> application -> domain
infrastructure -> application/domain ports
composition -> all layers
```

Domain не зависит ни от кого.

Application зависит от domain и port definitions.

Infrastructure реализует ports.

Interfaces вызывают use cases.

Composition собирает все части вместе.
