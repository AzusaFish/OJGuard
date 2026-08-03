import tempfile
import unittest
from pathlib import Path

from backend.app.domain import (
    AgentRunEventType,
    AgentRunStatus,
    IncidentStage,
    IncidentType,
    RouteDecision,
)
from backend.app.services.agent_routing import (
    AgentRoutingPolicy,
    InvalidRouteDecisionError,
)
from scripts.agentteams_runtime_control import _runtime, bootstrap, record_event


class AgentRunTests(unittest.TestCase):
    @staticmethod
    def temporary_directory():
        base = Path.cwd() / ".test-tmp"
        base.mkdir(exist_ok=True)
        return tempfile.TemporaryDirectory(dir=base)

    def test_events_are_sequenced_idempotent_and_queryable(self) -> None:
        with self.temporary_directory() as directory:
            root = Path(directory)
            initial = bootstrap(
                root,
                IncidentType.RUNTIME_REGRESSION,
                task_id="TASK-EVENTS",
                max_model_responses=8,
            )
            run_id = initial["agent_run"]["run_id"]

            first = record_event(
                root,
                run_id=run_id,
                event_id="EVENT-START",
                event_type=AgentRunEventType.RUN_STARTED,
                agent="ojguard-incident-manager",
                summary="Run started.",
                after_stage=IncidentStage.TRIAGING,
            )
            duplicate = record_event(
                root,
                run_id=run_id,
                event_id="EVENT-START",
                event_type=AgentRunEventType.RUN_STARTED,
                agent="ojguard-incident-manager",
                summary="Duplicate delivery must not create another event.",
                after_stage=IncidentStage.TRIAGING,
            )
            record_event(
                root,
                run_id=run_id,
                event_id="EVENT-ROUTE",
                event_type=AgentRunEventType.ROUTE_DECISION,
                agent="ojguard-incident-manager",
                worker="ojguard-signal-aggregator",
                action="triage",
                summary="Route triage.",
                before_stage=IncidentStage.TRIAGING,
                after_stage=IncidentStage.TRIAGING,
            )

            self.assertEqual(first["event"]["sequence"], duplicate["event"]["sequence"])
            repository, _ = _runtime(root)
            events = repository.list_agent_run_events(run_id)
            self.assertEqual([item.sequence for item in events], [1, 2, 3])
            run = repository.get_agent_run(run_id)
            self.assertIsNotNone(run)
            self.assertEqual(run.status, AgentRunStatus.RUNNING)
            self.assertEqual(run.model_response_count, 1)

    def test_policy_exposes_multiple_experiments_and_rejects_invalid_route(self) -> None:
        with self.temporary_directory() as directory:
            root = Path(directory)
            initial = bootstrap(root, IncidentType.RUNTIME_REGRESSION)
            incident_id = initial["incident_id"]
            repository, workflow = _runtime(root)
            workflow.begin_investigation(incident_id)
            workflow.propose_root_cause_hypotheses(incident_id)
            incident = repository.get_incident(incident_id)
            self.assertIsNotNone(incident)

            options = AgentRoutingPolicy(repository).legal_options(incident)
            self.assertEqual(len(options), 3)
            self.assertEqual(
                {item.experiment_kind for item in options},
                {
                    "cross_image_and_node_replay",
                    "cross_image_replay",
                    "cross_node_replay",
                },
            )
            selected = options[1]
            valid = RouteDecision(
                action=selected.action,
                worker=selected.worker,
                experiment_kind=selected.experiment_kind,
                reason="Choose a bounded discriminating comparison.",
                evidence_refs=selected.evidence_refs,
                expected_result=selected.expected_result,
            )
            self.assertEqual(AgentRoutingPolicy.validate_decision(valid, options), selected)
            invalid = valid.model_copy(update={"worker": "ojguard-impact-analyst"})
            with self.assertRaises(InvalidRouteDecisionError):
                AgentRoutingPolicy.validate_decision(invalid, options)


if __name__ == "__main__":
    unittest.main()
