import os
from pathlib import Path
import unittest
import uuid

from streamlit.testing.v1 import AppTest


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'Perlu database uji untuk AppTest')
class UiTests(unittest.TestCase):
    def setUp(self):
        self.previous=os.environ.get('DATABASE_URL')
        os.environ['DATABASE_URL']=os.environ['TEST_DATABASE_URL']
        self.app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30)

    def tearDown(self):
        if self.previous is None: os.environ.pop('DATABASE_URL',None)
        else: os.environ['DATABASE_URL']=self.previous

    def test_balanced_button_enabled_and_empty_reference_disabled(self):
        at=self.app.run()
        self.assertFalse(at.exception)
        self.assertFalse(at.button(key='submit_voucher').disabled)
        next(x for x in at.text_input if x.label=='Nomor bukti').set_value('').run()
        self.assertTrue(at.button(key='submit_voucher').disabled)

    def test_unbalanced_button_disabled(self):
        at=self.app.run()
        key='journal_editor_'+at.session_state['voucher_key']
        at.session_state[key]={'edited_rows':{1:{'Kredit':200000.0}},'added_rows':[],'deleted_rows':[]}
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(at.button(key='submit_voucher').disabled)

    def test_post_from_ui(self):
        at=self.app.run()
        next(x for x in at.text_input if x.label=='Nomor bukti').set_value('UI-'+uuid.uuid4().hex[:12]).run()
        at.button(key='submit_voucher').click().run()
        self.assertFalse(at.exception)
        self.assertTrue(any('berhasil diposting' in s.value for s in at.success))

    def test_added_blank_account_is_rejected_without_crash(self):
        at=self.app.run()
        key='journal_editor_'+at.session_state['voucher_key']
        at.session_state[key]={'edited_rows':{},'added_rows':[{'Akun':None,'Debit':1.0,'Kredit':0.0}],'deleted_rows':[]}
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(at.button(key='submit_voucher').disabled)
        self.assertTrue(any('belum memilih akun' in s.value for s in at.warning))

    def test_empty_nominal_not_coerced_to_zero(self):
        at=self.app.run()
        key='journal_editor_'+at.session_state['voucher_key']
        at.session_state[key]={'edited_rows':{0:{'Kredit':None}},'added_rows':[],'deleted_rows':[]}
        at.run()
        self.assertFalse(at.exception)
        self.assertTrue(at.button(key='submit_voucher').disabled)

    def test_success_resets_form_generation(self):
        at=self.app.run()
        old_key=at.session_state['voucher_key']
        next(x for x in at.text_input if x.label=='Nomor bukti').set_value('RESET-'+uuid.uuid4().hex[:12]).run()
        at.button(key='submit_voucher').click().run()
        self.assertFalse(at.exception)
        self.assertNotEqual(old_key,at.session_state['voucher_key'])
        self.assertFalse(at.button(key='submit_voucher').disabled)
