import json
import os
import smtplib
import sys
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import praw

# ==== CONFIGURAÇÕES DE BUSCA ====
subreddits = [
    'starvingartists', 'commisionshub', 'gameDevClassifieds', 'furry_catwalk',
    'HungryArtists', 'hireanartist', 'FurryCommissions', 'dndcommissions',
    'DnDart', 'commissions', 'artstore', 'Artistsforhire', 'artistforhire',
    'artcommission', 'AnimeCommission',
]
keywords = ['looking for', 'hiring']
exclude_keywords = [
    'for hire', 'for commission', 'commissions open',
    'Illustrator looking for work', 'Artist Looking for work',
    'Comic Book Artist Looking',
]

# Ignora posts mais velhos que isso (em horas). Evita receber posts antigos
# na primeira execução ou depois de uma pausa.
MAX_IDADE_HORAS = 3

# Arquivo que guarda os posts já enviados (o GitHub Actions salva ele no repositório)
ARQUIVO_VISTOS = 'seen_ids.json'

# ==== CREDENCIAIS (vêm dos Secrets do GitHub, nunca ficam no código) ====
REDDIT_ID = os.environ['REDDIT_ID']
REDDIT_SECRET = os.environ['REDDIT_SECRET']
EMAIL_USER = os.environ['EMAIL_USER']   # e-mail que ENVIA (Gmail)
EMAIL_PASS = os.environ['EMAIL_PASS']   # Senha de app do Gmail
EMAIL_TO = os.environ['EMAIL_TO']       # e-mail que RECEBE

reddit = praw.Reddit(
    client_id=REDDIT_ID,
    client_secret=REDDIT_SECRET,
    user_agent='python:monitor-commissions:v1.0 (by /u/S0BERANAART)',
    check_for_updates=False,
)


def carregar_vistos():
    if os.path.exists(ARQUIVO_VISTOS):
        with open(ARQUIVO_VISTOS, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def salvar_vistos(vistos):
    # Mantém só os 1000 mais recentes para o arquivo não crescer pra sempre
    with open(ARQUIVO_VISTOS, 'w', encoding='utf-8') as f:
        json.dump(vistos[-1000:], f)


def enviar_email(assunto, corpo):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_TO
    msg['Subject'] = assunto
    msg.attach(MIMEText(corpo, 'plain', 'utf-8'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
    print(f'E-mail enviado: {assunto}')


def main():
    vistos = carregar_vistos()
    vistos_set = set(vistos)
    agora = time.time()
    encontrados = []

    for nome in subreddits:
        try:
            for submission in reddit.subreddit(nome).new(limit=20):
                if submission.id in vistos_set:
                    continue
                if agora - submission.created_utc > MAX_IDADE_HORAS * 3600:
                    continue

                titulo = submission.title.lower()
                tem_keyword = any(k.lower() in titulo for k in keywords)
                excluido = any(e.lower() in titulo for e in exclude_keywords)

                if tem_keyword and not excluido:
                    encontrados.append({
                        'id': submission.id,
                        'titulo': submission.title,
                        'link': f'https://www.reddit.com{submission.permalink}',
                        'subreddit': nome,
                    })
                    print(f'Novo post em r/{nome}: {submission.title}')
        except Exception as e:
            print(f'Erro ao acessar r/{nome}: {e}')

    if not encontrados:
        print('Nenhum post novo neste ciclo.')
        return

    corpo = 'Olá Soberana,\n\nForam encontrados novos posts com suas palavras-chave:\n\n'
    for item in encontrados:
        corpo += f"Subreddit: r/{item['subreddit']}\n"
        corpo += f"Título: {item['titulo']}\n"
        corpo += f"Link: {item['link']}\n"
        corpo += '-' * 30 + '\n\n'

    # Só marca como "visto" DEPOIS que o e-mail foi enviado com sucesso.
    # Se o envio falhar, o erro para o script e o post será tentado de novo.
    enviar_email('Novos Posts do Reddit Encontrados!', corpo)
    vistos.extend(item['id'] for item in encontrados)
    salvar_vistos(vistos)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'Erro fatal: {e}')
        sys.exit(1)
