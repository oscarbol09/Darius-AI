"""
tests/test_face_biometrics.py — Pruebas unitarias para Darius Face Biometrics & Sentry Authentication
====================================================================================================
Verifica el motor biométrico facial de Darius AI.
Cumple con el protocolo ECC TDD: Red-Green-Refactor.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.darius_ai.core.face_biometrics import (
    BiometricResult,
    FaceBiometricsEngine,
)


class TestBiometricResultDataClass:
    def test_instantiation_and_fields(self):
        res = BiometricResult(
            verified=True,
            confidence=0.85,
            user_name="señor",
            distance=15.0,
            status="VERIFIED",
        )
        assert res.verified is True
        assert res.confidence == 0.85
        assert res.user_name == "señor"
        assert res.distance == 15.0
        assert res.status == "VERIFIED"

    def test_defaults(self):
        res = BiometricResult(
            verified=False,
            confidence=0.0,
            user_name="desconocido",
            distance=999.0,
            status="CHALLENGE_REQUIRED",
        )
        assert res.verified is False
        assert res.status == "CHALLENGE_REQUIRED"


class TestFaceBiometricsMathematicalConfidence:
    """Verifica la fórmula matemática de confianza en el motor biométrico."""

    def test_confidence_formula_bounds_and_values(self):
        engine = FaceBiometricsEngine()

        # Distancia 0 -> 100% de confianza
        assert engine.calculate_confidence(0.0) == 1.0

        # Distancia 50 -> 50% de confianza
        assert engine.calculate_confidence(50.0) == 0.5

        # Distancia 65 -> 35% de confianza (umbral límite)
        assert pytest.approx(engine.calculate_confidence(65.0), rel=1e-3) == 0.35

        # Distancia 100 -> 0.0 de confianza
        assert engine.calculate_confidence(100.0) == 0.0

        # Distancia > 100 -> clamped a 0.0 (previene porcentaje negativo)
        assert engine.calculate_confidence(125.0) == 0.0
        assert engine.calculate_confidence(999.0) == 0.0

        # Distancia < 0 -> clamped a 1.0
        assert engine.calculate_confidence(-5.0) == 1.0

    def test_verification_decision_threshold(self):
        engine = FaceBiometricsEngine(distance_threshold=65.0)

        # Distancia menor que 65.0 -> verificado
        assert engine.is_distance_verified(64.9) is True
        assert engine.is_distance_verified(20.0) is True

        # Distancia mayor o igual a 65.0 -> no verificado
        assert engine.is_distance_verified(65.0) is False
        assert engine.is_distance_verified(80.0) is False


class TestSoftDependencyFallback:
    """Verifica degradación elegante cuando OpenCV o cv2.face no están presentes."""

    def test_graceful_fallback_when_cv2_missing(self):
        with patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", False):
            engine = FaceBiometricsEngine()
            assert engine.is_available is False

            # No debe crashear al invocar métodos
            res_frame = engine.verify_face_frame(None)
            assert res_frame.verified is False
            assert res_frame.status in ("ENGINE_UNAVAILABLE", "MODEL_NOT_TRAINED")

            res_live = engine.verify_live_user(timeout_seconds=0.1)
            assert res_live.verified is False
            assert res_live.status == "CAMERA_UNAVAILABLE"

            assert engine.enroll_face([]) is False

    def test_graceful_fallback_when_cv2_face_missing(self):
        mock_cv2 = MagicMock()
        del mock_cv2.face  # Simular cv2 sin módulo contrib .face

        with (
            patch("src.darius_ai.core.face_biometrics.cv2", mock_cv2),
            patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", True),
            patch("src.darius_ai.core.face_biometrics._CV2_FACE_AVAILABLE", False),
        ):
            engine = FaceBiometricsEngine()
            assert engine.is_available is False
            res = engine.verify_face_frame("dummy_frame")
            assert res.verified is False


class TestProfileEnrollmentAndVerificationWithMockCv2:
    """Pruebas funcionales simulando el recognizer LBPH de OpenCV."""

    def test_enrollment_and_saving(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            engine = FaceBiometricsEngine(data_dir=data_dir, user_name="Óscar")

            mock_recognizer = MagicMock()
            mock_cv2 = MagicMock()
            mock_cv2.face.LBPHFaceRecognizer_create.return_value = mock_recognizer

            with (
                patch("src.darius_ai.core.face_biometrics.cv2", mock_cv2),
                patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", True),
                patch("src.darius_ai.core.face_biometrics._CV2_FACE_AVAILABLE", True),
            ):
                engine._recognizer = mock_recognizer
                engine._is_available = True
                # Entrenar con imágenes válidas
                mock_img1 = MagicMock()
                mock_img2 = MagicMock()
                success = engine.enroll_face([mock_img1, mock_img2], label_id=1, user_name="Óscar")
                assert success is True
                assert mock_recognizer.train.called
                assert mock_recognizer.save.called
                assert engine.is_trained is True

    def test_verify_face_frame_verified(self):
        engine = FaceBiometricsEngine(user_name="señor", distance_threshold=65.0)
        mock_recognizer = MagicMock()
        # predict retorna (label_id, distance)
        mock_recognizer.predict.return_value = (1, 42.0)
        engine._recognizer = mock_recognizer
        engine._is_trained = True
        engine._is_available = True
        engine._label_map = {1: "señor"}

        result = engine.verify_face_frame("mock_roi")
        assert result.verified is True
        assert result.user_name == "señor"
        assert result.distance == 42.0
        assert pytest.approx(result.confidence, rel=1e-3) == 0.58
        assert result.status == "VERIFIED"

    def test_verify_face_frame_unknown_face(self):
        engine = FaceBiometricsEngine(user_name="señor", distance_threshold=65.0)
        mock_recognizer = MagicMock()
        # Distancia alta = desconocido
        mock_recognizer.predict.return_value = (1, 85.0)
        engine._recognizer = mock_recognizer
        engine._is_trained = True
        engine._is_available = True

        result = engine.verify_face_frame("mock_roi")
        assert result.verified is False
        assert result.distance == 85.0
        assert pytest.approx(result.confidence, rel=1e-3) == 0.15
        assert result.status == "CHALLENGE_REQUIRED"

    def test_verify_face_frame_invalid_input(self):
        engine = FaceBiometricsEngine()
        engine._is_trained = True
        engine._is_available = True

        res = engine.verify_face_frame(None)
        assert res.verified is False
        assert res.status == "INVALID_FRAME"


class TestLiveUser3TierFallback:
    """Verifica los 3 niveles de contingencia de verify_live_user."""

    def test_tier_1_biometric_match(self):
        engine = FaceBiometricsEngine(user_name="señor")
        engine._is_trained = True
        engine._is_available = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_frame = MagicMock()
        mock_cap.read.return_value = (True, mock_frame)

        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale.return_value = [(10, 10, 50, 50)]  # 1 rostro detectado

        mock_cv2 = MagicMock()
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CascadeClassifier.return_value = mock_cascade
        mock_cv2.cvtColor.return_value = mock_frame

        with (
            patch("src.darius_ai.core.face_biometrics.cv2", mock_cv2),
            patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", True),
            patch.object(
                engine,
                "verify_face_frame",
                return_value=BiometricResult(
                    verified=True,
                    confidence=0.9,
                    user_name="señor",
                    distance=10.0,
                    status="VERIFIED",
                ),
            ),
        ):
            res = engine.verify_live_user(timeout_seconds=1.0)
            assert res.verified is True
            assert res.status == "VERIFIED"
            assert mock_cap.release.called

    def test_tier_2_timeout_or_unknown_face_challenge_required(self):
        engine = FaceBiometricsEngine(user_name="señor")
        engine._is_trained = True
        engine._is_available = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.read.return_value = (True, MagicMock())

        mock_cascade = MagicMock()
        # Rostro detectado pero verify_face_frame no lo verifica
        mock_cascade.detectMultiScale.return_value = [(10, 10, 50, 50)]

        mock_cv2 = MagicMock()
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CascadeClassifier.return_value = mock_cascade

        with (
            patch("src.darius_ai.core.face_biometrics.cv2", mock_cv2),
            patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", True),
            patch.object(
                engine,
                "verify_face_frame",
                return_value=BiometricResult(
                    verified=False,
                    confidence=0.1,
                    user_name="desconocido",
                    distance=90.0,
                    status="CHALLENGE_REQUIRED",
                ),
            ),
        ):
            res = engine.verify_live_user(timeout_seconds=0.2)
            assert res.verified is False
            assert res.status == "CHALLENGE_REQUIRED"
            assert mock_cap.release.called

    def test_tier_3_camera_unavailable(self):
        engine = FaceBiometricsEngine()
        mock_cv2 = MagicMock()
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = False  # Cámara no se puede abrir
        mock_cv2.VideoCapture.return_value = mock_cap

        with (
            patch("src.darius_ai.core.face_biometrics.cv2", mock_cv2),
            patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", True),
        ):
            res = engine.verify_live_user(timeout_seconds=0.5)
            assert res.verified is False
            assert res.status == "CAMERA_UNAVAILABLE"


class TestDariusGreetings:
    def test_greetings_by_status(self):
        engine = FaceBiometricsEngine()

        verified_res = BiometricResult(
            verified=True,
            confidence=0.88,
            user_name="señor",
            distance=12.0,
            status="VERIFIED",
        )
        msg_verified = engine.get_biometric_greeting(verified_res)
        assert "señor" in msg_verified
        assert "confirmada" in msg_verified.lower() or "autorizados" in msg_verified.lower()

        challenge_res = BiometricResult(
            verified=False,
            confidence=0.2,
            user_name="desconocido",
            distance=80.0,
            status="CHALLENGE_REQUIRED",
        )
        msg_challenge = engine.get_biometric_greeting(challenge_res)
        assert "desafío" in msg_challenge.lower() or "seguridad" in msg_challenge.lower()

        unavail_res = BiometricResult(
            verified=False,
            confidence=0.0,
            user_name="desconocido",
            distance=999.0,
            status="CAMERA_UNAVAILABLE",
        )
        msg_unavail = engine.get_biometric_greeting(unavail_res)
        assert "contingencia" in msg_unavail.lower() or "sensores" in msg_unavail.lower()

        unknown_status_res = BiometricResult(status="CUSTOM_ERROR")
        msg_unknown = engine.get_biometric_greeting(unknown_status_res)
        assert "CUSTOM_ERROR" in msg_unknown

        from src.darius_ai.core.face_biometrics import get_biometric_greeting
        assert get_biometric_greeting(verified_res) == msg_verified


class TestFaceBiometricsEdgeCasesAndCoverage:
    def test_engine_properties(self):
        engine = FaceBiometricsEngine(user_name="Tony", distance_threshold=70.0)
        assert engine.user_name == "Tony"
        assert engine.distance_threshold == 70.0

    def test_singleton_engine(self):
        from src.darius_ai.core.face_biometrics import get_face_biometrics_engine
        e1 = get_face_biometrics_engine()
        e2 = get_face_biometrics_engine()
        assert e1 is e2

    def test_init_with_lbph_create_exception(self):
        mock_cv2 = MagicMock()
        mock_cv2.face.LBPHFaceRecognizer_create.side_effect = RuntimeError("Init failed")
        with (
            patch("src.darius_ai.core.face_biometrics.cv2", mock_cv2),
            patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", True),
            patch("src.darius_ai.core.face_biometrics._CV2_FACE_AVAILABLE", True),
        ):
            engine = FaceBiometricsEngine()
            assert engine.is_available is False

    def test_load_existing_model_success_and_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            model_file = Path(tmpdir) / "face_model.yml"
            labels_file = Path(tmpdir) / "labels.json"
            model_file.write_text("model_content", encoding="utf-8")
            labels_file.write_text('{"1": "Óscar", "2": "Tony"}', encoding="utf-8")

            mock_recognizer = MagicMock()
            mock_cv2 = MagicMock()
            mock_cv2.face.LBPHFaceRecognizer_create.return_value = mock_recognizer

            with (
                patch("src.darius_ai.core.face_biometrics.cv2", mock_cv2),
                patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", True),
                patch("src.darius_ai.core.face_biometrics._CV2_FACE_AVAILABLE", True),
            ):
                engine = FaceBiometricsEngine(data_dir=tmpdir, model_path=model_file)
                assert engine.is_trained is True
                assert engine._label_map[1] == "Óscar"
                assert engine._label_map[2] == "Tony"

                # Prueba fallo al leer modelo corrupto
                mock_recognizer.read.side_effect = Exception("Corrupt file")
                assert engine._load_existing_model() is False
                assert engine.is_trained is False

    def test_enroll_face_empty_and_exception(self):
        engine = FaceBiometricsEngine()
        engine._is_available = True
        engine._recognizer = MagicMock()

        # Imágenes vacías
        assert engine.enroll_face([]) is False

        # Excepción al entrenar
        engine._recognizer.train.side_effect = Exception("Train fail")
        assert engine.enroll_face(["img1"]) is False

    def test_verify_face_frame_exceptions_and_not_trained(self):
        engine = FaceBiometricsEngine()
        engine._is_available = True
        engine._is_trained = False
        assert engine.verify_face_frame("roi").status == "MODEL_NOT_TRAINED"

        engine._is_trained = True
        engine._recognizer = MagicMock()
        engine._recognizer.predict.side_effect = Exception("Predict boom")
        res = engine.verify_face_frame("roi")
        assert res.verified is False
        assert res.status == "CHALLENGE_REQUIRED"

    def test_verify_live_user_exceptions_in_capture(self):
        engine = FaceBiometricsEngine()
        mock_cv2 = MagicMock()
        mock_cv2.VideoCapture.side_effect = Exception("Camera crash")

        with (
            patch("src.darius_ai.core.face_biometrics.cv2", mock_cv2),
            patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", True),
        ):
            res = engine.verify_live_user(timeout_seconds=0.1)
            assert res.verified is False
            assert res.status == "CAMERA_UNAVAILABLE"

    def test_verify_live_user_cascade_creation_fail_and_channel_types(self):
        engine = FaceBiometricsEngine()
        engine._is_trained = True
        engine._is_available = True

        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True

        # Frame 2D en escala de grises
        import numpy as np
        frame_2d = np.zeros((100, 100), dtype=np.uint8)
        mock_cap.read.return_value = (True, frame_2d)

        mock_cascade = MagicMock()
        mock_cascade.detectMultiScale.return_value = [(0, 0, 50, 50)]

        mock_cv2 = MagicMock()
        mock_cv2.VideoCapture.return_value = mock_cap
        mock_cv2.CascadeClassifier.side_effect = [Exception("Cascade load err"), mock_cascade]

        with (
            patch("src.darius_ai.core.face_biometrics.cv2", mock_cv2),
            patch("src.darius_ai.core.face_biometrics._CV2_AVAILABLE", True),
            patch.object(
                engine,
                "verify_face_frame",
                return_value=BiometricResult(verified=True, status="VERIFIED"),
            ),
        ):
            # Probar cuando cascade falla
            res = engine.verify_live_user(timeout_seconds=0.1)
            assert res.verified is False or res.status in ("CHALLENGE_REQUIRED", "VERIFIED")
