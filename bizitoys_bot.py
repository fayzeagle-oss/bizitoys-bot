import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# === SOZLAMALAR ===
BOT_TOKEN = "8643289539:AAHMrcGQFhjKqwUOEO-OAWXUKYlBAKllszk"
ADMIN_ID = 296474181

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

orders = []
order_counter = [1]

# ==============================
# MAHSULOTLARNI YUKLASH
# ==============================
def load_products():
    try:
        with open("products.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

PRODUCTS = load_products()
logger.info(f"{len(PRODUCTS)} ta mahsulot yuklandi")

# ==============================
# BOSHLASH
# ==============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("🧸 Katalogni ko'rish", callback_data="catalog_0")],
        [InlineKeyboardButton("🛒 Buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("📞 Aloqa", callback_data="contact")],
    ]
    await update.message.reply_text(
        f"Salom, {user.first_name}! 👋\n\n"
        f"🧸 *BiziToys* do'koniga xush kelibsiz!\n\n"
        f"Bizda *{len(PRODUCTS)}* ta mahsulot mavjud!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==============================
# KATALOG (sahifalash)
# ==============================
PAGE_SIZE = 10

async def show_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = int(query.data.split("_")[1])
    start_idx = page * PAGE_SIZE
    end_idx = start_idx + PAGE_SIZE
    page_products = PRODUCTS[start_idx:end_idx]

    if not page_products:
        await query.edit_message_text("Mahsulotlar topilmadi.")
        return

    keyboard = []
    text = f"🧸 *Katalog* (sahifa {page+1}/{(len(PRODUCTS)-1)//PAGE_SIZE+1}):\n\n"

    for p in page_products:
        stock_text = f"{p['stock']} ta" if p['stock'] > 0 else "tugagan"
        text += f"• *{p['name']}* — {p['price']:,} so'm ({stock_text})\n"
        if p['stock'] > 0:
            keyboard.append([InlineKeyboardButton(
                f"🛍 {p['name'][:35]}",
                callback_data=f"product_{p['id']}"
            )])

    # Navigatsiya
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"catalog_{page-1}"))
    if end_idx < len(PRODUCTS):
        nav.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"catalog_{page+1}"))
    if nav:
        keyboard.append(nav)

    keyboard.append([InlineKeyboardButton("🔍 Qidirish", callback_data="search")])
    keyboard.append([InlineKeyboardButton("🔙 Orqaga", callback_data="back_main")])

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==============================
# QIDIRISH
# ==============================
async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["order_step"] = "search"
    await query.edit_message_text(
        "🔍 *Qidirish*\n\nMahsulot nomini kiriting:",
        parse_mode="Markdown"
    )

async def search_products(text, update, context):
    results = [p for p in PRODUCTS if text.lower() in p['name'].lower()]
    if not results:
        await update.message.reply_text(
            f"😔 '{text}' bo'yicha hech narsa topilmadi.\n\n"
            "Boshqa so'z bilan qidiring.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Katalogga", callback_data="catalog_0")
            ]])
        )
        return

    keyboard = []
    result_text = f"🔍 *'{text}' natijalari ({len(results)} ta):*\n\n"
    for p in results[:15]:
        stock_text = f"{p['stock']} ta" if p['stock'] > 0 else "tugagan"
        result_text += f"• *{p['name']}* — {p['price']:,} so'm ({stock_text})\n"
        if p['stock'] > 0:
            keyboard.append([InlineKeyboardButton(
                f"🛍 {p['name'][:35]}",
                callback_data=f"product_{p['id']}"
            )])

    keyboard.append([InlineKeyboardButton("🔙 Katalogga", callback_data="catalog_0")])
    await update.message.reply_text(
        result_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==============================
# MAHSULOT TAFSILOTI
# ==============================
async def product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    product_id = int(query.data.split("_")[1])
    prod = next((p for p in PRODUCTS if p["id"] == product_id), None)

    if not prod:
        await query.edit_message_text("Mahsulot topilmadi.")
        return

    keyboard = []
    if prod['stock'] > 0:
        max_qty = min(prod['stock'], 5)
        qty_buttons = [InlineKeyboardButton(f"{q} ta", callback_data=f"qty_{product_id}_{q}") for q in range(1, max_qty + 1)]
        keyboard.append(qty_buttons)
    keyboard.append([InlineKeyboardButton("🔙 Katalogga qaytish", callback_data="catalog_0")])

    text = (
        f"🧸 *{prod['name']}*\n\n"
        f"💰 Narxi: *{prod['price']:,} so'm*\n"
        f"📦 Omborda: *{prod['stock']} ta*\n"
    )
    if prod.get("desc"):
        text += f"\n📝 {prod['desc']}"

    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ==============================
# MIQDOR TANLASH
# ==============================
async def select_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    product_id = int(parts[1])
    quantity = int(parts[2])
    context.user_data["ordering_product"] = product_id
    context.user_data["ordering_quantity"] = quantity
    context.user_data["order_step"] = "name"
    prod = next((p for p in PRODUCTS if p["id"] == product_id), None)
    await query.edit_message_text(
        f"📝 *Buyurtma berish*\n\n"
        f"🧸 {prod['name']}\n"
        f"🔢 Miqdor: *{quantity} ta*\n"
        f"💰 Jami: *{prod['price'] * quantity:,} so\'m*\n\n"
        f"Ismingizni kiriting:",
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
    context.user_data["ordering_quantity"] = 1
    context.user_data["order_step"] = "name"
    await query.edit_message_text(
        "📝 *Buyurtma berish*\n\nIsmingizni kiriting:",
        parse_mode="Markdown"
    )

async def handle_order_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get("order_step")

    if step == "search":
        context.user_data["order_step"] = None
        await search_products(update.message.text, update, context)

    elif step == "name":
        context.user_data["order_name"] = update.message.text
        context.user_data["order_step"] = "phone"
        await update.message.reply_text("📱 Telefon raqamingizni kiriting (+998XXXXXXXXX):")

    elif step == "phone":
        context.user_data["order_phone"] = update.message.text
        context.user_data["order_step"] = "address"
        await update.message.reply_text("📍 Manzilingizni kiriting:")

    elif step == "address":
        context.user_data["order_address"] = update.message.text
        context.user_data["order_step"] = None

        order_id = order_counter[0]
        order_counter[0] += 1

        product_id = context.user_data.get("ordering_product", 1)
        prod = next((p for p in PRODUCTS if p["id"] == product_id), {"name": "Noma'lum", "price": 0})

        quantity = context.user_data.get("ordering_quantity", 1)
        total_price = prod["price"] * quantity
        order = {
            "id": order_id,
            "user_id": update.effective_user.id,
            "user_name": context.user_data["order_name"],
            "phone": context.user_data["order_phone"],
            "address": context.user_data["order_address"],
            "product": prod["name"],
            "quantity": quantity,
            "price": total_price,
            "status": "Yangi"
        }
        orders.append(order)

        await update.message.reply_text(
            f"✅ *Buyurtmangiz qabul qilindi!*\n\n"
            f"🔢 Buyurtma №: *{order_id}*\n"
            f"🧸 Mahsulot: *{prod['name']}*\n"
            f"🔢 Miqdor: *{quantity} ta*\n"
            f"💰 Jami narx: *{total_price:,} so'm*\n"
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
                        f"🔢 Miqdor: {quantity} ta\n"
                        f"💰 Jami: {total_price:,} so'm"
                    ),
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{order_id}"),
                        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"cancel_{order_id}")
                    ]])
                )
            except Exception as e:
                logger.warning(f"Admin xabari: {e}")

# ==============================
# ADMIN TASDIQLASH
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
                text=f"✅ Buyurtmangiz №{order_id} *tasdiqlandi!* Tez orada yetkazib beramiz. 🚀",
                parse_mode="Markdown"
            )
        except: pass
    elif action == "cancel":
        order["status"] = "Bekor qilindi"
        await query.edit_message_text(f"❌ Buyurtma №{order_id} bekor qilindi.")
        try:
            await context.bot.send_message(
                chat_id=order["user_id"],
                text=f"❌ Buyurtmangiz №{order_id} bekor qilindi. Admin bilan bog'laning."
            )
        except: pass

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
            text += f"{emoji} №{o['id']} — {o['product'][:30]} — {o['status']}\n"
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
        [InlineKeyboardButton("🧸 Katalogni ko'rish", callback_data="catalog_0")],
        [InlineKeyboardButton("🛒 Buyurtmalarim", callback_data="my_orders")],
        [InlineKeyboardButton("📞 Aloqa", callback_data="contact")],
    ]
    await query.edit_message_text(
        "🏠 *Bosh menyu*",
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
    await update.message.reply_text(
        f"📊 *Statistika:*\n\n"
        f"🧸 Mahsulotlar: *{len(PRODUCTS)} ta*\n"
        f"📦 Jami buyurtmalar: *{total}*\n"
        f"✅ Tasdiqlangan: *{confirmed}*\n"
        f"⏳ Kutilmoqda: *{pending}*\n"
        f"💰 Daromad: *{revenue:,} so'm*",
        parse_mode="Markdown"
    )

# ==============================
# MAIN
# ==============================
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(show_catalog, pattern="^catalog_\\d+$"))
    app.add_handler(CallbackQueryHandler(search_start, pattern="^search$"))
    app.add_handler(CallbackQueryHandler(my_orders, pattern="^my_orders$"))
    app.add_handler(CallbackQueryHandler(contact, pattern="^contact$"))
    app.add_handler(CallbackQueryHandler(back_main, pattern="^back_main$"))
    app.add_handler(CallbackQueryHandler(product_detail, pattern="^product_\\d+$"))
    app.add_handler(CallbackQueryHandler(select_quantity, pattern="^qty_\\d+_\\d+$"))
    app.add_handler(CallbackQueryHandler(place_order, pattern="^order_\\d+$"))
    app.add_handler(CallbackQueryHandler(admin_action, pattern="^(confirm|cancel)_\\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_input))
    print("✅ Bot ishga tushdi! 796 ta mahsulot yuklandi.")
    app.run_polling()

if __name__ == "__main__":
    main()
