import notekeeper.application as application
import notekeeper.application.commands as commands
import notekeeper.application.results as results
import notekeeper.application.use_cases as use_cases
import notekeeper.application.use_cases.campaigns as campaign_use_cases
import notekeeper.application.use_cases.export as export_use_cases
import notekeeper.application.use_cases.processing as processing_use_cases


def test_application_reexports_public_api() -> None:
    assert application.CreateCampaign is use_cases.CreateCampaign
    assert application.CreateCampaignCommand is commands.CreateCampaignCommand
    assert application.CreateCampaignResult is results.CreateCampaignResult
    assert application.CreateProcessingJobForAudioTrack is (
        use_cases.CreateProcessingJobForAudioTrack
    )
    assert application.CreateProcessingJobForAudioTrackCommand is (
        commands.CreateProcessingJobForAudioTrackCommand
    )
    assert application.CreateProcessingJobForAudioTrackResult is (
        results.CreateProcessingJobForAudioTrackResult
    )
    assert application.RestartFailedProcessingJob is (
        use_cases.RestartFailedProcessingJob
    )
    assert application.RestartFailedProcessingJobCommand is (
        commands.RestartFailedProcessingJobCommand
    )
    assert application.RestartFailedProcessingJobResult is (
        results.RestartFailedProcessingJobResult
    )
    assert application.RunProcessingJob is use_cases.RunProcessingJob
    assert application.TranscriptChunk is results.TranscriptChunk


def test_use_case_packages_reexport_expected_classes() -> None:
    assert use_cases.CreateCampaign is campaign_use_cases.CreateCampaign
    assert use_cases.AddParticipantToCampaign is (
        campaign_use_cases.AddParticipantToCampaign
    )
    assert use_cases.AddVoiceSample is campaign_use_cases.AddVoiceSample
    assert use_cases.SubmitRecordingForProcessing is (
        processing_use_cases.SubmitRecordingForProcessing
    )
    assert use_cases.CreateProcessingJobForAudioTrack is (
        processing_use_cases.CreateProcessingJobForAudioTrack
    )
    assert use_cases.RestartFailedProcessingJob is (
        processing_use_cases.RestartFailedProcessingJob
    )
    assert use_cases.RunProcessingJob is processing_use_cases.RunProcessingJob
    assert use_cases.ReviewSpeakerMappings is processing_use_cases.ReviewSpeakerMappings
    assert use_cases.GenerateRecap is processing_use_cases.GenerateRecap
    assert use_cases.GetJobStatus is processing_use_cases.GetJobStatus
    assert use_cases.ExportTranscriptMarkdown is (
        export_use_cases.ExportTranscriptMarkdown
    )
    assert use_cases.ExportRecapMarkdown is export_use_cases.ExportRecapMarkdown
