"""Run a single local Codex task with ephemeral session storage and an isolated home."""
import json, os, pathlib, shutil, subprocess, tempfile, urllib.request, tomllib

def main():
    here=pathlib.Path(__file__).resolve().parent
    cli=shutil.which('codex')
    if not cli: raise RuntimeError('Codex CLI was not found.')
    with urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=5) as r:
        health=json.load(r)
    print('上下文档位：1 = 64K 日常（默认），2 = 32K 较早压缩')
    tier=input('选择档位 [1/2]：').strip()
    expected=32768 if tier=='2' else 65536
    if not health.get('loaded') or health.get('max_context',0)<expected:
        raise RuntimeError(f'Start Strata with at least {expected} context tokens first.')
    print('本地 Codex：单次临时会话，正常退出后清理临时目录；不会修改桌面版默认模型。')
    print('允许在指定工作目录内读写，以及联网访问网址。当前识图尚未配置完成。')
    workspace=pathlib.Path(input('工作目录（绝对路径）：').strip().strip('"'))
    if not workspace.is_absolute() or not workspace.is_dir():
        raise ValueError('请输入已存在的绝对目录路径。')
    prompt=input('本次任务：').strip()
    if not prompt:return
    with tempfile.TemporaryDirectory(prefix='strata-codex-') as private_home:
        cfg='model_instructions_file = '+json.dumps(str(here/'local-agent-instructions.txt'))+'\n'
        cfg+='model_catalog_json = '+json.dumps(str(here/'strata-models.json'))+'\n'
        cfg+=(here/'local-codex.config.toml').read_text(encoding='utf-8')
        if expected==32768:
            cfg=cfg.replace('model_context_window = 65536','model_context_window = 32768').replace('model_auto_compact_token_limit = 49152','model_auto_compact_token_limit = 24576')
        pathlib.Path(private_home,'config.toml').write_text(cfg,encoding='utf-8')
        env=os.environ.copy();env['CODEX_HOME']=private_home;env['RUST_LOG']='off'
        result=subprocess.run([cli,'exec','--ephemeral','--strict-config','--skip-git-repo-check','-s','workspace-write','-C',str(workspace),'-'],input=prompt,text=True,encoding='utf-8',env=env)
        print('任务退出码：',result.returncode)

if __name__=='__main__':
    try:main()
    except Exception as exc:print('启动失败：',exc)
    input('按回车关闭。')
