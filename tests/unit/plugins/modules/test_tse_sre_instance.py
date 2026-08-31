from ansible_collections.susunola.tencentcloud.plugins.modules import tse_sre_instance


class Module(object):
    def fail_json(self,**kwargs): raise AssertionError(kwargs)


def test_wait_requires_expected_engine_state(monkeypatch):
    values=iter([
        {"Status":"running","EnableInternet":False},
        {"Status":"running","EnableInternet":True},
    ])
    monkeypatch.setattr(tse_sre_instance,"find",lambda *args:next(values))
    monkeypatch.setattr(tse_sre_instance.time,"sleep",lambda delay:None)
    result=tse_sre_instance._wait(Module(),object(),object(),{"waiter_timeout":10,"waiter_delay":0},["running"],{"EnableInternet":True})
    assert result["EnableInternet"] is True


def test_wait_requires_engine_absence(monkeypatch):
    values=iter([{"Status":"deleting"},None])
    monkeypatch.setattr(tse_sre_instance,"find",lambda *args:next(values))
    monkeypatch.setattr(tse_sre_instance.time,"sleep",lambda delay:None)
    assert tse_sre_instance._wait(Module(),object(),object(),{"waiter_timeout":10,"waiter_delay":0},absent=True) is None
