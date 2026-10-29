"""Exact issued-URL byte upload, with native admission and no account secrets."""

from dataclasses import dataclass, field
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import ssl
import stat
from urllib.parse import urlsplit

from .http import OutcomeUnknown, ProviderError


@dataclass(frozen=True)
class UploadTarget:
    url: str = field(repr=False)
    method: str
    headers: dict = field(default_factory=dict, repr=False)

    def validate(self):
        u = urlsplit(self.url)
        if (u.scheme != 'https' or not u.hostname or u.username or u.password
                or u.port not in {None,443} or u.fragment or self.method not in {'PUT','POST'}):
            raise ValueError('Use the exact original issued HTTPS upload target')
        if any(k.lower() in {'authorization','cookie','proxy-authorization'} for k in self.headers):
            raise ValueError('Account credentials cannot be forwarded to an issued media URL')
        return u


def _frozen_file(artifact):
    path = Path(artifact['path'])
    if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('The original media input must be an absolute native file')
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size != artifact['size']:
        raise ValueError('The original frozen media size changed')
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            digest.update(block)
    if digest.hexdigest() != artifact['sha256']:
        raise ValueError('The original frozen media hash changed')
    return path, before


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _send(target, artifact, path, before, *, offset, length, before_dispatch,
          connection_factory, part_number=None, whole_digest=None):
    u = target.validate()
    if _identity(path.stat()) != _identity(before):
        raise ValueError('The original frozen media changed before upload')
    headers = dict(target.headers)
    if any(k.lower()=='content-length' and str(v)!=str(length) for k,v in headers.items()):
        raise ValueError('Issued upload length differs from the frozen bytes')
    if not callable(before_dispatch):
        raise ValueError('The original native upload owner must admit these exact bytes')
    before_dispatch({'operation':'issued_media_upload','media_sha256':artifact['sha256'],
                     'bytes':length,'offset':offset,'part_number':part_number,
                     'target_sha256':hashlib.sha256(target.url.encode()).hexdigest(), 'method':target.method})
    connection = connection_factory(u.hostname,443,timeout=60,context=ssl.create_default_context())
    digest = hashlib.sha256();sent=0
    try:
        connection.putrequest(target.method,u.path+('?' + u.query if u.query else ''))
        for name,value in headers.items():
            connection.putheader(name,str(value))
        if not any(k.lower()=='content-length' for k in headers):
            connection.putheader('Content-Length',str(length))
        connection.endheaders()
        with path.open('rb') as source:
            if _identity(os.fstat(source.fileno())) != _identity(before):
                raise OutcomeUnknown('Original upload input identity changed')
            source.seek(offset)
            while sent < length:
                block = source.read(min(1024*1024, length-sent))
                if not block:
                    raise OutcomeUnknown('Original upload input was truncated')
                sent+=len(block);digest.update(block)
                if whole_digest is not None:
                    whole_digest.update(block)
                connection.send(block)
        after=path.stat()
        if (sent!=length or _identity(before)!=_identity(after) or
                offset==0 and length==before.st_size and digest.hexdigest()!=artifact['sha256']):
            raise OutcomeUnknown('Frozen input changed during an admitted media upload')
        response=connection.getresponse();body=response.read(65537)
        if len(body)>65536:
            raise OutcomeUnknown('The original upload returned an oversized acknowledgement')
        if not 200<=response.status<300:
            raise ProviderError(response.status,'issued_upload_refused')
        return {'status':response.status,'bytes':sent,'sha256':digest.hexdigest(),'etag':response.getheader('ETag')}
    except (OSError,TimeoutError,http.client.HTTPException):
        raise OutcomeUnknown('The original media upload needs reconciliation; it was not retried') from None
    finally:
        connection.close()


def upload_exact(target, artifact, *, before_dispatch, connection_factory=http.client.HTTPSConnection):
    target.validate()
    path, before = _frozen_file(artifact)
    return _send(target, artifact, path, before, offset=0, length=before.st_size,
                 before_dispatch=before_dispatch, connection_factory=connection_factory)


def upload_multipart(signed_parts, artifact, *, before_dispatch, after_part,
                     connection_factory=http.client.HTTPSConnection, require_etags=True,
                     completed_parts=None):
    """One bounded sequential pass; the caller saves each original ETag.

    Retrying a part, selecting new URLs and committing processing belong to the
    original owner, so an interruption never restarts this function automatically.
    """
    if not callable(after_part) or not isinstance(signed_parts, list) or not signed_parts:
        raise ValueError('The caller must retain every original multipart receipt')
    count = len(signed_parts)
    if count > 10000 or [p.get('partNumber') for p in signed_parts] != list(range(1,count+1)):
        raise ValueError('Use the complete original ordered multipart targets')
    targets = [UploadTarget(p['url'], 'PUT') for p in signed_parts]
    for target in targets:
        target.validate()
    path, before = _frozen_file(artifact)
    chunk = math.ceil(before.st_size / count)
    if not before.st_size or (count-1)*chunk >= before.st_size:
        raise ValueError('Original multipart targets do not fit the frozen bytes')
    whole_digest, receipts = hashlib.sha256(), []
    completed={p['partNumber']:p for p in (completed_parts or [])}
    if set(completed)-set(range(1,count+1)):
        raise ValueError('Retained multipart receipt belongs to another original target')
    for index, target in enumerate(targets):
        offset = index * chunk
        if index+1 in completed:
            original=completed[index+1];length=min(chunk,before.st_size-offset);part_digest=hashlib.sha256()
            with path.open('rb') as source:
                source.seek(offset);remaining=length
                while remaining:
                    block=source.read(min(1024*1024,remaining))
                    if not block:raise ValueError('Retained multipart source was truncated')
                    remaining-=len(block);part_digest.update(block);whole_digest.update(block)
            if (original.get('offset')!=offset or original.get('bytes')!=length
                    or original.get('sha256')!=part_digest.hexdigest() or require_etags and not original.get('etag')):
                raise ValueError('Retained multipart receipt differs from the frozen original bytes')
            receipts.append(original)
            continue
        result = _send(target, artifact, path, before, offset=offset,
                       length=min(chunk, before.st_size-offset), part_number=index+1,
                       before_dispatch=before_dispatch, connection_factory=connection_factory,
                       whole_digest=whole_digest)
        etag = result['etag']
        if not etag and require_etags:
            raise OutcomeUnknown('An original multipart upload returned no ETag; no part was replayed')
        # The actual native uploader JSON-decodes the quoted HTTP ETag.
        try:
            decoded = json.loads(etag)
        except (TypeError, ValueError):
            decoded = etag
        if (not isinstance(decoded, str) or not decoded) and require_etags:
            raise OutcomeUnknown('Original multipart ETag is malformed')
        receipt = {'partNumber':index+1,'etag':decoded, 'bytes':result['bytes'],
                   'sha256':result['sha256'], 'offset':offset, 'status':result['status']}
        try:
            after_part(receipt)
        except Exception:
            raise OutcomeUnknown('Original uploaded part lacks durable native receipt; no replay was made') from None
        receipts.append(receipt)
    if whole_digest.hexdigest() != artifact['sha256']:
        raise OutcomeUnknown('Original multipart bytes changed; processing was not committed')
    return [{'partNumber':r['partNumber'], 'etag':r['etag']} for r in receipts]
