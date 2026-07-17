import notekeeper.application as application
import notekeeper.application.commands as commands
import notekeeper.application.results as results
import notekeeper.application.use_cases as use_cases
import notekeeper.application.use_cases.campaigns as campaign_use_cases
import notekeeper.application.use_cases.export as export_use_cases
import notekeeper.application.use_cases.processing as processing_use_cases


def test_application_reexports_public_api() -> None:
    assert application.CancelProcessingJob is use_cases.CancelProcessingJob
    assert application.CancelProcessingJobCommand is (
        commands.CancelProcessingJobCommand
    )
    assert application.CancelProcessingJobResult is results.CancelProcessingJobResult
    assert application.ClearFailedJobsForCampaign is (
        use_cases.ClearFailedJobsForCampaign
    )
    assert application.ClearFailedJobsForCampaignCommand is (
        commands.ClearFailedJobsForCampaignCommand
    )
    assert application.ClearFailedJobsForCampaignResult is (
        results.ClearFailedJobsForCampaignResult
    )
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
    assert application.DeleteProcessingJob is use_cases.DeleteProcessingJob
    assert application.DeleteProcessingJobCommand is (
        commands.DeleteProcessingJobCommand
    )
    assert application.DeleteProcessingJobResult is results.DeleteProcessingJobResult
    assert application.RestartFailedProcessingJob is (
        use_cases.RestartFailedProcessingJob
    )
    assert application.RestartFailedProcessingJobCommand is (
        commands.RestartFailedProcessingJobCommand
    )
    assert application.RestartFailedProcessingJobResult is (
        results.RestartFailedProcessingJobResult
    )
    assert application.RestartProcessingJob is use_cases.RestartProcessingJob
    assert application.RestartProcessingJobCommand is (
        commands.RestartProcessingJobCommand
    )
    assert application.RestartProcessingJobResult is results.RestartProcessingJobResult
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
    assert use_cases.ClearFailedJobsForCampaign is (
        processing_use_cases.ClearFailedJobsForCampaign
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
