import logging
import asyncio
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# === SOZLAMALAR ===
BOT_TOKEN = "8643289539:AAHMrcGQFhjKqwUOEO-OAWXUKYlBAKllszk"
ADMIN_ID = 296474181
BILLZ_API_KEY = "fd1ba0f78a4fbb50519270ad795260e5c13b1063a6ab78f21c29a3b5c68811f88178aef803869cdb1d70e23d5a46e29c0979dd7688938227d09e1bfd5f581486ba8c0a7218ca83e0296a23c3f3f3f0cdd550387dfa140c182f0f1dc15f3a4a98c662b3ea95e070d0b572ba0ab3de9d647419323ac109ee4d"
BILLZ_API_URL = "https://api.billz.io/v2"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

orders = []
order_counter = [1]
products_cache = []

# ==============================
# BILLZ DAN MAHSULOTLAR OLISH
# ==============================
def get_billz_products():
    global products_cache
    try:
        headers = {
            "X-API-KEY": BILLZ_API_KEY,
            "Content-Type": "application/json"
        }
        response = requests.get(
            f"{BILLZ_API_URL}/products",
            headers=headers,
            params={"limit": 50, "offset": 0}
        )
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", data.get("products", data.get("items", [])))
            products_cache = []
            for i, item in enumerate(items):
                name = item.get("name", item.get("title", f"Mahsulot {i+1}"))
                # Narxni olish
                price = 0
                if "price" in item:
                    price = item["price"]
                elif "retail_price" in item:
                    price = item["retail_price"]
                elif "selling_price" in item:
                    price = item["selling_price"]
                # Rasmni olish
                photo = None
                if "image" in item and item["image"]:
                    photo = item["image"]
                elif "images" in item and item["images"]:
                    photo = item["images"][0] if isinstance(item["images"], list) else item["images"]
                # Miqdorni olish
                stock = item.get("quantity", item.get("stock", item.get("amount", 0)))

                products_cache.append({
                    "id": i + 1,
                    "billz_id": item.get("id", str(i)),
                    "name": name,
                    "price": int(price),
                    "stock": int(stock) if stock else 0,
                    "photo": photo,
                    "desc": item.get("description", "")
                })
            logger.info(f"Billz dan {len(products_cache)} ta mahsulot olindi")
            return products_cache
        else:
            logger.warning(f"Billz API xato: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        logger.error(f"Billz ulanish xatosi: {e}")
        return []

def get_products():
    if not products_cache:
        return get_billz_products()
    return products_cache

# ==============================
# BOSHLASH
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🧸 Katalogni ko'rish", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("📞 Aloqa", callback_data="contact")],
    ]
    await update.message.reply_text(
        f"Salom, {user.first_name}! 👋\n\n"
        f"🧸 *BiziToys* do'koniga xush kelibsiz!\n\n"
        f"Quyidagi tugmalardan foydalaning:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==============================
# KATALOG
# ==============================
async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text("⏳ Mahsulotlar yuklanmoqda...")

    prod_list = get_products()

    if not prod_list:
        await query.edit_message_text(
            "😔 Hozir mahsulotlar mavjud emas.\n\nIltimos, keyinroq urinib ko'ring.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]])
        )
        return

    keyboard = []
    text = "🧸 *Mahsulotlar katalogi:*\n\n"
    for p in prod_list:
        stock_text = f"({p['stock']} ta)" if p['stock'] > 0 else "(tugagan)"
        text += f"• *{p['name']}* — {p['price']:,} so'm {stock_text}\n"
        if p['stock'] > 0:
            keyboard.append([InlineKeyboardButton(
                f"🛍 {p['name']} - {p['price']:,} so'm",
                callback_data=f"product_{p['id']}"
            )])

    keyboard.append([InlineKeyboardButton("🔄 Yangilash", callback_data="refresh_catalog")])
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def refresh_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Yangilanmoqda...")
    global products_cache
    products_cache = []
    await show_catalog(update, context)

# ==============================
# MAHSULOT TAFSILOTI
# ==============================
async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_")[1])
    prod_list = get_products()
    prod = next((p for p in prod_list if p["id"] == product_id), None)

    if not prod:
        await query.edit_message_text("Mahsulot topilmadi.")
        return

    keyboard = [
        [InlineKeyboardButton("✅ Buyurtma berish", callback_data=f"order_{product_id}")],
        [InlineKeyboardButton("🔙 Katalogga qaytish", callback_data="catalog")],
    ]

    text = (
        f"🧸 *{prod['name']}*\n\n"
        f"💰 Narxi: *{prod['price']:,} so'm*\n"
        f"📦 Omborda: *{prod['stock']} ta*\n"
    )
    if prod.get("desc"):
        text += f"\n📝 {prod['desc']}"

    if prod.get("photo"):
        try:
            await query.message.reply_photo(
                photo=prod["photo"],
                caption=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            await query.message.delete()
            return
        except:
            pass

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==============================
# BUYURTMA BERISH
# ==============================
async def place_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_")[1])
    context.user_data["ordering_product"] = product_id
    context.user_data["order_step"] = "name"

    await query.edit_message_text(
        "📝 *Buyurtma berish*\n\n"
        "Ismingizni kiriting:",
        parse_mode="Markdown"
    )

async def handle_order_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("order_step")

    if step == "name":
        context.user_data["order_name"] = update.message.text
        context.user_data["order_step"] = "phone"
        await update.message.reply_text("📱 Telefon raqamingizni kiriting (masalan: +998901234567):")

    elif step == "phone":
        context.user_data["order_phone"] = update.message.text
        context.user_data["order_step"] = "address"
        await update.message.reply_text("📍 Manzilingizni kiriting:")

    elif step == "address":
        context.user_data["order_address"] = update.message.text
        context.user_data["order_step"] = None

        order_id = order_counter[0]
        order_counter[0] += 1

        prod_list = get_products()
        product_id = context.user_data.get("ordering_product", 1)
        prod = next((p for p in prod_list if p["id"] == product_id), {"name": "Noma'lum", "price": 0})

        order = {
            "id": order_id,
            "user_id": update.effective_user.id,
            "user_name": context.user_data["order_name"],
            "phone": context.user_data["order_phone"],
            "address": context.user_data["order_address"],
            "product": prod["name"],
            "price": prod["price"],
            "status": "Yangi"
        }
        orders.append(order)

        await update.message.reply_text(
            f"✅ *Buyurtmangiz qabul qilindi!*\n\n"
            f"🔢 Buyurtma №: *{order_id}*\n"
            f"🧸 Mahsulot: *{prod['name']}*\n"
            f"💰 Narx: *{prod['price']:,} so'm*\n"
            f"📍 Manzil: {order['address']}\n\n"
            f"Tez orada siz bilan bog'lanamiz! 📞",
            parse_mode="Markdown"
        )

        if ADMIN_ID:
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=(
                        f"🔔 *Yangi buyurtma №{order_id}!*\n\n"
                        f"👤 Mijoz: {order['user_name']}\n"
                        f"📱 Tel: {order['phone']}\n"
                        f"📍 Manzil: {order['address']}\n"
                        f"🧸 Mahsulot: {prod['name']}\n"
                        f"💰 Narx: {prod['price']:,} so'm"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{order_id}"),
                            InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{order_id}")
                        ]
                    ])
                )
            except Exception as e:
                logger.warning(f"Adminga xabar yuborishda xato: {e}")

# ==============================
# ADMIN: TASDIQLASH / BEKOR QILISH
# ==============================
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action, order_id = query.data.split("_")
    order_id = int(order_id)

    order = next((o for o in orders if o["id"] == order_id), None)
    if not order:
        await query.edit_message_text("Buyurtma topilmadi.")
        return

    if action == "confirm":
        order["status"] = "Tasdiqlandi"
        await query.edit_message_text(f"✅ Buyurtma №{order_id} tasdiqlandi.")
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"✅ Buyurtmangiz №{order_id} *tasdiqlandi!*\nTez orada yetkazib beramiz. 🚀",
                parse_mode="Markdown"
            )
        except:
            pass
    elif action == "cancel":
        order["status"] = "Bekor qilindi"
        await query.edit_message_text(f"❌ Buyurtma №{order_id} bekor qilindi.")
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"❌ Buyurtmangiz №{order_id} bekor qilindi.\nSabab uchun admin bilan bog'laning.",
            )
        except:
            pass

# ==============================
# BUYURTMALARIM
# ==============================
async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_orders = [o for o in orders if o["user_id"] == user_id]

    if not user_orders:
        text = "📋 Sizda hozircha buyurtma yo'q."
    else:
        text = "📋 *Sizning buyurtmalaringiz:*\n\n"
        for o in user_orders:
            emoji = "✅" if o["status"] == "Tasdiqlandi" else "⏳" if o["status"] == "Yangi" else "❌"
            text += f"{emoji} №{o['id']} — {o['product']} — {o['status']}\n"

    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# ==============================
# ALOQA
# ==============================
async def contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")]]
    await query.edit_message_text(
        "📞 *Biz bilan bog'laning:*\n\n"
        "📱 Telefon: +998 XX XXX XX XX\n"
        "📍 Manzil: Toshkent\n"
        "🕐 Ish vaqti: 9:00 - 18:00",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==============================
# ORQAGA
# ==============================
async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🧸 Katalogni ko'rish", callback_data="catalog")],
        [InlineKeyboardButton("🛒 Buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("📞 Aloqa", callback_data="contact")],
    ]
    await query.edit_message_text(
        "🏠 *Bosh menyu*\n\nNima qilmoqchisiz?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==============================
# STATISTIKA
# ==============================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Ruxsat yo'q.")
        return

    total = len(orders)
    confirmed = len([o for o in orders if o["status"] == "Tasdiqlandi"])
    pending = len([o for o in orders if o["status"] == "Yangi"])
    revenue = sum(o["price"] for o in orders if o["status"] == "Tasdiqlandi")
    prod_count = len(get_products())

    await update.message.reply_text(
        f"📊 *Statistika:*\n\n"
        f"🧸 Billz mahsulotlar: *{prod_count} ta*\n"
        f"📦 Jami buyurtmalar: *{total}*\n"
        f"✅ Tasdiqlangan: *{confirmed}*\n"
        f"⏳ Kutilmoqda: *{pending}*\n"
        f"💰 Daromad: *{revenue:,} so'm*",
        parse_mode="Markdown"
    )

async def reload_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Ruxsat yo'q.")
        return
    global products_cache
    products_cache = []
    prods = get_billz_products()
    await update.message.reply_text(f"✅ Billz dan {len(prods)} ta mahsulot yangilandi!")

# ==============================
# ASOSIY FUNKSIYA
# ==============================
def main():
    # Billz dan mahsulotlarni oldindan yuklash
    logger.info("Billz dan mahsulotlar yuklanmoqda...")
    get_billz_products()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("reload", reload_products))

    app.add_handler(CallbackQueryHandler(show_catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(refresh_catalog, pattern="^refresh_catalog$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(contact, pattern="^contact$"))
    app.add_handler(CallbackQueryHandler(back_main, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(product_detail, pattern="^product_\\d+$"))
    app.add_handler(CallbackQueryHandler(place_order, pattern="^order_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(confirm|cancel)_\\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_input))

    print("✅ Bot ishga tushdi! Billz bilan ulandi.")
    app.run_polling()

if __name__ == "__main__":
    main()
