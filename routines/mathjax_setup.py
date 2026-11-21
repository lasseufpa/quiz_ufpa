"""Cópia local do MathJax para as aulas funcionarem sem internet.

O script (`tex-chtml.js`) e as fontes CHTML vêm de pacotes npm diferentes:

    static/mathjax/tex-chtml.js
    static/@mathjax/mathjax-newcm-font/chtml/{woff2,dynamic}/

Na primeira execução com internet, `ensure_local_assets` baixa os dois (~3 MB)
em segundo plano: o servidor sobe normalmente e, assim que os arquivos chegam,
as próximas páginas passam a carregar tudo do disco. Sem internet, nada é
gravado e o layout continua usando o CDN (com uma nova tentativa no próximo
start).

Os downloads são feitos num diretório temporário e só entram no lugar depois de
completos, então uma interrupção no meio do caminho nunca deixa o MathJax local
pela metade.
"""

import io
import json
import logging
import os
import shutil
import tarfile
import threading
import urllib.request

log = logging.getLogger(__name__)

# Versões usadas quando não há nenhuma cópia local para servir de referência.
DEFAULT_VERSION = '4.1.3'

SCRIPT_URL = 'https://cdn.jsdelivr.net/npm/mathjax@{version}/tex-chtml.js'
FONTS_URL = (
    'https://registry.npmjs.org/@mathjax/mathjax-newcm-font/-/'
    'mathjax-newcm-font-{version}.tgz'
)

SCRIPT_FILE = os.path.join('mathjax', 'tex-chtml.js')
SCRIPT_VERSION_FILE = os.path.join('mathjax', '.mathjax-version')
FONTS_DIR = os.path.join('@mathjax', 'mathjax-newcm-font')
FONTS_PACKAGE_FILE = os.path.join(FONTS_DIR, 'package.json')
# Subpastas do pacote de fontes que o CHTML pede em tempo de execução.
FONTS_SUBDIRS = ('chtml/woff2', 'chtml/dynamic')

_lock = threading.Lock()
_started = False


def has_local_script(static_folder):
    """O bundle do MathJax já está em `static/mathjax/`?"""
    return os.path.isfile(os.path.join(static_folder, SCRIPT_FILE))


def has_local_fonts(static_folder):
    """O pacote de fontes CHTML está completo em `static/@mathjax/`?"""
    return all(
        os.path.isdir(os.path.join(static_folder, FONTS_DIR, *sub.split('/')))
        for sub in FONTS_SUBDIRS
    )


def has_local_assets(static_folder):
    """Script e fontes estão ambos no disco (é o que o layout exige)."""
    return has_local_script(static_folder) and has_local_fonts(static_folder)


def local_version(static_folder):
    """Versão do MathJax já presente no disco, se houver como descobrir."""
    candidates = (
        (os.path.join(static_folder, 'mathjax', 'package.json'), 'json'),
        (os.path.join(static_folder, SCRIPT_VERSION_FILE), 'text'),
        (os.path.join(static_folder, FONTS_PACKAGE_FILE), 'json'),
    )
    for path, kind in candidates:
        try:
            with open(path, encoding='utf-8') as f:
                if kind == 'json':
                    version = json.load(f).get('version')
                else:
                    version = f.read().strip()
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(version, str) and version.strip():
            return version.strip()
    return None


def ensure_local_assets(static_folder):
    """Dispara (uma vez por processo) o download do que estiver faltando.

    Retorna a thread do download, ou None quando nada precisa ser baixado.
    """
    global _started
    with _lock:
        if _started:
            return None
        _started = True
        missing_script = not has_local_script(static_folder)
        missing_fonts = not has_local_fonts(static_folder)

    if not (missing_script or missing_fonts):
        return None

    thread = threading.Thread(
        target=_install,
        args=(static_folder, missing_script, missing_fonts),
        name='mathjax-setup',
        daemon=True,
    )
    thread.start()
    return thread


def _install(static_folder, missing_script, missing_fonts):
    version = local_version(static_folder) or DEFAULT_VERSION
    log.info(f"Baixando MathJax {version} para uso offline (só na primeira vez)...")
    try:
        if missing_script:
            _install_script(static_folder, version)
        if missing_fonts:
            _install_fonts(static_folder, version)
    except Exception as e:  # rede, HTTP, tar corrompido...
        log.warning(
            f"Não foi possível baixar o MathJax ({e}). As fórmulas vão usar o "
            f"CDN até a próxima execução do app com internet."
        )
        return
    log.info(
        f"MathJax local pronto em '{static_folder}': as fórmulas funcionam "
        f"sem internet."
    )


def _fetch(url, timeout=120):
    request = urllib.request.Request(
        url, headers={'User-Agent': 'quiz-ufpa (+https://github.com/lasseufpa/quiz_ufpa)'}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _install_script(static_folder, version):
    target_dir = os.path.join(static_folder, 'mathjax')
    os.makedirs(target_dir, exist_ok=True)

    data = _fetch(SCRIPT_URL.format(version=version))
    final = os.path.join(static_folder, SCRIPT_FILE)
    tmp = f'{final}.tmp'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, final)

    with open(os.path.join(static_folder, SCRIPT_VERSION_FILE), 'w', encoding='utf-8') as f:
        f.write(version + '\n')


def _install_fonts(static_folder, version):
    parent = os.path.join(static_folder, '@mathjax')
    os.makedirs(parent, exist_ok=True)
    staging = os.path.join(parent, '.mathjax-newcm-font.tmp')
    shutil.rmtree(staging, ignore_errors=True)

    data = _fetch(FONTS_URL.format(version=version))
    extracted = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name
            if name == 'package/package.json':
                rel = 'package.json'
            else:
                # Só as pastas que o CHTML consulta em tempo de execução.
                rel = next(
                    (name[len('package/'):] for sub in FONTS_SUBDIRS
                     if name.startswith(f'package/{sub}/')),
                    None,
                )
                if rel is None:
                    continue
            dest = os.path.join(staging, *rel.split('/'))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with tar.extractfile(member) as src, open(dest, 'wb') as out:
                shutil.copyfileobj(src, out)
            extracted += 1

    if not extracted:
        raise RuntimeError('pacote de fontes do MathJax sem os arquivos esperados')

    final = os.path.join(static_folder, FONTS_DIR)
    shutil.rmtree(final, ignore_errors=True)
    os.replace(staging, final)
