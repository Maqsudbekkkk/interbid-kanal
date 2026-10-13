# INTERBID kanali: avtomatik postlar

Bu repo @inter_bid Telegram kanaliga postlarni o'z vaqtida joylaydi. Postlar @INTERBIDAIBOT boti orqali chiqadi, kanalda esa kanal nomidan ko'rinadi.

## Qanday ishlaydi

- Har bir post `posts/` papkasida alohida `.txt` fayl.
- GitHub Actions har kuni Toshkent vaqti bilan 09:00, 11:00, 12:00 va 13:00 da (har soatda ikki marta) ishga tushadi va vaqti kelgan postlarni joylaydi.
- Joylangan postlar `state/sent.json` fayliga yoziladi, shuning uchun hech bir post ikki marta chiqmaydi.
- 12 soatdan ko'p kechikkan post yuborilmaydi, faqat "o'tkazib yuborildi" deb belgilanadi.
- Xato bo'lsa, Actions'da qizil belgi chiqadi va GitHub sizga email yuboradi.

## Post fayli

Fayl nomi: `YYYY-MM-DD-SSMM-mavzu.txt`, masalan `2026-10-17-1100-taklif.txt`.

Oddiy post:

```
at: 2026-10-17T11:00:00+05:00
type: message
---
🎁 <b>Sarlavha</b>

Matn. Havola: <a href="https://interbidacademy.uz">sayt</a>
```

So'rovnoma:

```
at: 2026-10-16T13:00:00+05:00
type: poll
---
Savol matni?
- 1-variant
- 2-variant
```

Formatlash HTML'da: `<b>qalin</b>`, `<i>kursiv</i>`, `<a href="...">havola</a>`. Matn 4096 belgidan oshmasligi kerak.

## Kerakli sozlama

Settings → Secrets and variables → Actions → **New repository secret**:
- Name: `TELEGRAM_BOT_TOKEN`
- Secret: BotFather bergan token

## Qo'lda boshqarish

- Postni bekor qilish: faylni o'chiring.
- Postni o'zgartirish: faylni tahrirlang (joylanmasdan oldin).
- Darhol joylash: Actions → "Kanalga post joylash" → **Run workflow**. Vaqti kelgan postlar shu zahoti chiqadi.
