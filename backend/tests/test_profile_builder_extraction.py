import unittest

from backend.app.api.profile_builder import _build_profile


class ProfileBuilderExtractionTest(unittest.TestCase):
    def test_extracts_fields_by_step(self) -> None:
        profile = _build_profile(
            [
                "\u6211\u662f\u8f6f\u4ef6\u5de5\u7a0b\u4e13\u4e1a\u5927\u4e8c\u5b66\u751f\uff0c"
                "\u5f53\u524d\u5b66\u4e60\u4eba\u5de5\u667a\u80fd\u8bfe\u7a0b\uff0c"
                "CNN\u548c\u53cd\u5411\u4f20\u64ad\u6bd4\u8f83\u8584\u5f31\u3002",
                "\u51c6\u5907\u671f\u672b\u8003\u8bd5\u3001\u638c\u63e1\u6838\u5fc3\u6982\u5ff5\u3002",
                "CNN\u548c\u53cd\u5411\u4f20\u64ad",
                "\u559c\u6b22\u5148\u770b\u8bb2\u4e49\uff0c\u518d\u505a\u7ec3\u4e60\u9898\uff0c"
                "\u4e5f\u5e0c\u671b\u6709\u4ee3\u7801\u6848\u4f8b\u3002",
                "\u6211\u4e60\u60ef\u5148\u770b\u6574\u4f53\u6846\u67b6\uff0c"
                "\u518d\u7ed3\u5408\u6848\u4f8b\u9010\u6b65\u63a8\u5bfc\u3002",
                "\u76ee\u524d\u662f\u57fa\u7840\u6c34\u5e73\u3002",
            ]
        )

        self.assertEqual(profile["major"], "\u8f6f\u4ef6\u5de5\u7a0b")
        self.assertEqual(profile["grade"], "\u5927\u4e8c")
        self.assertEqual(profile["course"], "\u4eba\u5de5\u667a\u80fd")
        self.assertEqual(
            profile["goal"],
            "\u51c6\u5907\u671f\u672b\u8003\u8bd5\u3001\u638c\u63e1\u6838\u5fc3\u6982\u5ff5",
        )
        self.assertEqual(profile["weak_points"], ["CNN", "\u53cd\u5411\u4f20\u64ad"])
        self.assertEqual(
            profile["preference"],
            "\u5148\u770b\u8bb2\u4e49\uff0c\u518d\u505a\u7ec3\u4e60\u9898\uff0c"
            "\u4e5f\u5e0c\u671b\u6709\u4ee3\u7801\u6848\u4f8b",
        )
        self.assertEqual(
            profile["cognitive_style"],
            "\u5148\u770b\u6574\u4f53\u6846\u67b6\uff0c"
            "\u518d\u7ed3\u5408\u6848\u4f8b\u9010\u6b65\u63a8\u5bfc",
        )
        self.assertEqual(profile["knowledge_level"], "\u57fa\u7840\u6c34\u5e73")

    def test_keeps_goal_and_preference_in_their_own_steps(self) -> None:
        profile = _build_profile(
            [
                "\u8f6f\u4ef6\u5de5\u7a0b\u4e13\u4e1a\uff0c\u5927\u4e8c\uff0c"
                "\u60f3\u5b66\u4e60\u4eba\u5de5\u667a\u80fd\u3002",
                "\u638c\u63e1\u6838\u5fc3\u6982\u5ff5\u5e76\u51c6\u5907\u671f\u672b\u8003\u8bd5\u3002",
                "",
                "\u559c\u6b22\u5148\u770b\u8bb2\u4e49\uff0c\u518d\u505a\u7ec3\u4e60\u9898\u3002",
            ]
        )

        self.assertEqual(
            profile["goal"],
            "\u638c\u63e1\u6838\u5fc3\u6982\u5ff5\u5e76\u51c6\u5907\u671f\u672b\u8003\u8bd5",
        )
        self.assertEqual(
            profile["preference"],
            "\u5148\u770b\u8bb2\u4e49\uff0c\u518d\u505a\u7ec3\u4e60\u9898",
        )
        self.assertEqual(len(profile), 8)


if __name__ == "__main__":
    unittest.main()
