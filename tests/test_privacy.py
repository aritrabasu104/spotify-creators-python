"""No real accounts are needed for the publication and error privacy checks."""
import ast
from pathlib import Path
import re
import sys
import traceback
import unittest
from urllib.error import URLError

from spotify_creators.http import HttpTransport, OutcomeUnknown, TransportUnavailable

ROOT=Path(__file__).resolve().parents[1]
PACKAGE='spotify_creators'


def private_patterns(text):
    patterns=(r'/(?:Users|home)/[A-Za-z][^/\s"\x27]+/',
              r'[A-Z]:\\Users\\[^\\\s]+\\',
              r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
              r'gh[pousr]_[A-Za-z0-9]{20,}',
              r'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
    return any(re.search(pattern,text) for pattern in patterns)


class PublicationPrivacyTests(unittest.TestCase):
    def test_public_files_have_no_machine_paths_or_credential_blobs(self):
        files=list((ROOT/'src'/PACKAGE).glob('*.py'))
        files+=list((ROOT/'docs').glob('*.md'))+list((ROOT/'examples').glob('*.py'))
        files += [path for path in (ROOT/'README.md',ROOT/'pyproject.toml',ROOT/'SECURITY.md') if path.exists()]
        for path in files:
            with self.subTest(file=str(path.relative_to(ROOT))):
                self.assertFalse(private_patterns(path.read_text()))

    def test_package_imports_only_itself_and_declared_public_dependencies(self):
        allowed=set(sys.stdlib_module_names)|{PACKAGE}
        for path in (ROOT/'src'/PACKAGE).glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node,ast.Import):
                    for name in node.names:self.assertIn(name.name.split('.')[0],allowed,path.name)
                elif isinstance(node,ast.ImportFrom) and node.level==0:
                    self.assertIn(node.module.split('.')[0],allowed,path.name)

    def test_no_literal_account_secrets_in_package_configuration(self):
        sensitive={'access_token','refresh_token','client_secret','password','code_verifier','id_token','authorization','cookie','apikey'}
        for path in (ROOT/'src'/PACKAGE).glob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                pairs=[]
                if isinstance(node,ast.Dict):pairs=list(zip(node.keys,node.values))
                if isinstance(node,ast.Assign):
                    pairs=[(ast.Constant(target.id),node.value) for target in node.targets if isinstance(target,ast.Name)]
                for key,value in pairs:
                    if (isinstance(key,ast.Constant) and isinstance(key.value,str)
                        and key.value.lower() in sensitive and isinstance(value,ast.Constant)
                        and isinstance(value.value,str)):
                        self.assertFalse(value.value,path.name)


class ErrorPrivacyTests(unittest.TestCase):
    def test_transport_failure_tracebacks_exclude_sensitive_urls(self):
        marker='synthetic-private-query-value'
        class Broken:
            calls=0
            def open(self,*args,**kwargs):
                self.calls+=1
                raise URLError('https://example.invalid/?access_token='+marker)
        for mutation in (False,True):
            transport=HttpTransport();opener=Broken();transport.opener=opener
            with self.subTest(mutation=mutation):
                try:transport.execute('POST' if mutation else 'GET','https://api.spotify.com/v1/me',mutation=mutation)
                except (OutcomeUnknown,TransportUnavailable) as error:
                    rendered=''.join(traceback.format_exception(error))
                    self.assertNotIn(marker,rendered)
                    self.assertTrue(error.__suppress_context__)
                    self.assertEqual(opener.calls,1)
                else:self.fail('Expected a typed, sanitized transport failure')

    def test_issued_upload_failure_does_not_echo_its_signed_url(self):
        import hashlib
        import tempfile
        from spotify_creators.media import UploadTarget, upload_exact
        marker='synthetic-private-upload-query'
        class Connection:
            def __init__(self,*args,**kwargs):pass
            def putrequest(self,*args):pass
            def putheader(self,*args):pass
            def endheaders(self):pass
            def send(self,*args):pass
            def getresponse(self):raise OSError('https://example.invalid/?signature='+marker)
            def close(self):pass
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory).resolve()/'media.bin';path.write_bytes(b'example')
            frozen={'path':str(path),'size':7,'sha256':hashlib.sha256(b'example').hexdigest()}
            try:
                upload_exact(UploadTarget('https://example.invalid/upload?signature='+marker,'PUT'),
                    frozen,before_dispatch=lambda _:None,connection_factory=Connection)
            except OutcomeUnknown as error:
                self.assertNotIn(marker,''.join(traceback.format_exception(error)))
            else:self.fail('Expected the original upload to remain unknown')
