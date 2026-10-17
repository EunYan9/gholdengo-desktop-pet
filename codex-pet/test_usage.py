import math
import unittest
from codex_usage import parse_limits, QuotaError


def window(used,minutes):
    return {'usedPercent':used,'windowDurationMins':minutes,'resetsAt':1000}


class UsageTests(unittest.TestCase):
    def test_real_quota_windows_and_bottleneck(self):
        got=parse_limits({'rateLimitsByLimitId':{'codex':{
            'primary':window(14,300),'secondary':window(2,10080),
            'credits':{'balance':'0','hasCredits':False}}}})
        self.assertEqual([w['label'] for w in got['windows']],['5小时额度','周额度'])
        self.assertEqual(got['remaining'],86)
        self.assertFalse(got['blocked'])

    def test_prefer_codex_over_unrelated_bucket(self):
        got=parse_limits({'rateLimits':{'primary':window(99,300)},
            'rateLimitsByLimitId':{'codex':{'primary':window(20,300)},
                                  'other':{'primary':window(100,300)}}})
        self.assertEqual(got['remaining'],80)

    def test_missing_is_not_zero(self):
        for value in [None,True,float('nan'),float('inf'),'20']:
            with self.subTest(value=value):
                with self.assertRaises(QuotaError):
                    parse_limits({'rateLimits':{'primary':window(value,300)}})

    def test_legacy_and_backend_block(self):
        got=parse_limits({'ordinaryUsageAllowed':False,
                          'rateLimits':{'primary':window(2,300),'secondary':None}})
        self.assertTrue(got['blocked'])
        self.assertEqual(got['remaining'],98)
        self.assertEqual(len(got['windows']),1)

    def test_server_out_of_bounds_is_clamped(self):
        self.assertEqual(parse_limits({'rateLimits':{'primary':window(-2,300)}})['remaining'],100)
        self.assertEqual(parse_limits({'rateLimits':{'primary':window(102,300)}})['remaining'],0)


if __name__=='__main__':unittest.main()
