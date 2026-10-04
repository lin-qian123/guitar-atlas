"""Fully read repeated bibliographic music sentences; literal cited labels stay."""
import re
import build_cglib_review as cg
def label(s):return cg.PHRASES.get(cg.q.normphrase(s),s.strip(' .'))
def book_read(body):
 m=re.fullmatch(r'Le Delizie dell Italia,?\s*(?:select Italian Melodies from the operas of (.+?),?\s+c\.\s+)?for Guitar and Piano\s*,?\s*(?:arranged\.\s*)?No\.?\s*(\d+)\.\s*(.+)',body,re.I)
 if m:
  return '〈意大利之乐〉：意大利旋律精选（吉他与钢琴），第'+m[2]+'曲〈'+label(m[3])+'〉'+('；引用歌剧：'+m[1] if m[1] else '')
 m=re.fullmatch(r'Le Delizie dell Italia Guitar and Piano,?\s*(?:arranged\.\s*)?No\.\s*(\d+)\.\s*(.+)',body,re.I)
 if m:return '〈意大利之乐〉第'+m[1]+'曲〈'+label(m[2])+'〉（吉他与钢琴）'
 m=re.fullmatch(r'Douze Ouvertures des plus Célèbres Compositions, arrangées pour Guitare\s+Violon\. Première Livraison\. No\.\s*(\d+)\.\s*(.+)',body,re.I)
 if m:return '十二首著名作品序曲（吉他与小提琴改编），第一册第'+m[1]+'曲〈'+label(m[2])+'〉'
 m=re.fullmatch(r'Choix de Douze Ouvertures de la Composition de Rossini, arrangées pour Guitare\s+Piano\. No\.\s*(\d+)\.\s*(.+)',body,re.I)
 if m:return 'Rossini序曲十二首精选（吉他与钢琴改编），第'+m[1]+'曲〈'+label(m[2])+'〉'
 m=re.fullmatch(r'Potpourris für eine Guitarre über beliebte Opern Melodieen von Philipp Süssmann\. No\.\s*(\d+)\.\s*(.+)',body,re.I)
 if m:return '精选歌剧旋律吉他集成曲（原题署名Philipp Süssmann），第'+m[1]+'号〈'+label(m[2])+'〉'
 m=re.fullmatch(r'(.*?)\s*from Journal de Pièces de Musique pour la Guitare Tirées de divers Auteurs Espagnols\s*(?:autres)?\s*(?:s)?\s*(?:…\s*Chaque Cahier sera composé de trois Pièces ou un air varié dont un paraîtra tous les (?:trois mois|trois|))?',body,re.I)
 if m:
  heading=m[1].strip(' .')
  if not heading:return '选取西班牙等作曲家作品的吉他音乐期刊'
  translated,_=cg.full_music(heading)
  return (translated or '〈'+label(heading)+'〉')+'（选自〈西班牙等作曲家吉他作品期刊〉）'
 m=re.fullmatch(r'(seguidilla) from Journal de Pièces du chant Espagnol, par divers Auteurs, publiées avec Accompagnement de Guitares',body,re.I)
 if m:return '塞吉迪亚曲（选自各作曲家〈西班牙歌曲期刊〉，吉他伴奏）'
 m=re.fullmatch(r'Periodical Amusements for the Spanish Guitar\. No\. (\d+)',body,re.I)
 if m:return '西班牙吉他定期消遣曲集，第'+m[1]+'期'
 m=re.fullmatch(r'Title Periodical Amusements for the Spanish Guitar\. No\. (\d+)',body,re.I)
 if m:return '西班牙吉他定期消遣曲集，第'+m[1]+'期'
 return None
