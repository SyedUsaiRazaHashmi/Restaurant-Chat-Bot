from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
import os

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = 'deliciousbites-secret-2024'

# ============================================================================
# DATABASE SETUP
# ============================================================================

def init_database():
    """Initialize SQLite database with menu and orders tables"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Create menu table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            rating REAL,
            image TEXT
        )
    ''')
    
    # Create orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            customer_address TEXT NOT NULL,
            customer_phone TEXT NOT NULL,
            items TEXT NOT NULL,
            total_amount REAL NOT NULL,
            order_status TEXT DEFAULT 'Preparing',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert sample menu data
    cursor.execute('SELECT COUNT(*) FROM menu')
    if cursor.fetchone()[0] == 0:
        menu_items = [
            ('BBQ Chicken Pizza', 18.99, 'Hot Picks', 'Grilled chicken, BBQ sauce, red onions, mozzarella', 4.9, '🍕'),
            ('Supreme Deluxe', 21.99, 'Hot Picks', 'Pepperoni, sausage, mushrooms, bell peppers, olives', 4.8, '🍕'),
            ('Beef Burger Special', 14.99, 'Hot Picks', 'Premium Angus beef, aged cheddar, bacon, special sauce', 4.9, '🍔'),
            ('Margherita Classic', 12.99, 'Pizzas', 'Fresh mozzarella, tomato sauce, basil', 4.7, '🍕'),
            ('Pepperoni Feast', 16.99, 'Pizzas', 'Double pepperoni, extra cheese', 4.8, '🍕'),
            ('Veggie Supreme', 15.99, 'Pizzas', 'Mushrooms, bell peppers, onions, olives, tomatoes', 4.6, '🍕'),
            ('Chicken Crispy Burger', 12.99, 'Burgers', 'Crispy fried chicken, lettuce, mayo, pickles', 4.7, '🍔'),
            ('Double Stack Burger', 17.99, 'Burgers', 'Two beef patties, double cheese, grilled onions', 4.8, '🍔'),
            ('French Fries', 4.99, 'Sides', 'Crispy golden fries with seasoning', 4.5, '🍟'),
            ('Onion Rings', 5.99, 'Sides', 'Beer-battered crispy onion rings', 4.6, '🧅'),
            ('Mozzarella Sticks', 6.99, 'Sides', 'Breaded mozzarella with marinara sauce', 4.7, '🧀'),
            ('Coca Cola', 2.99, 'Beverages', 'Classic Coca Cola 330ml', 4.5, '🥤'),
            ('Fresh Lemonade', 3.99, 'Beverages', 'Freshly squeezed lemonade', 4.6, '🍋'),
            ('Iced Coffee', 4.99, 'Beverages', 'Cold brew coffee with ice', 4.7, '☕'),
        ]
        cursor.executemany('''
            INSERT INTO menu (name, price, category, description, rating, image)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', menu_items)
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully!")

# Initialize database on startup
init_database()

# ============================================================================
# DATABASE HELPER FUNCTIONS
# ============================================================================

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_all_menu_items():
    """Get all menu items"""
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM menu').fetchall()
    conn.close()
    return [dict(item) for item in items]

def get_menu_by_category(category):
    """Get menu items by category"""
    conn = get_db_connection()
    items = conn.execute('SELECT * FROM menu WHERE category = ?', (category,)).fetchall()
    conn.close()
    return [dict(item) for item in items]

def get_item_by_id(item_id):
    """Get specific menu item"""
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM menu WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    return dict(item) if item else None

def save_order(order_data):
    """Save order to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO orders (order_id, customer_name, customer_address, customer_phone, 
                          items, total_amount, order_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        order_data['order_id'],
        order_data['customer_name'],
        order_data['customer_address'],
        order_data['customer_phone'],
        json.dumps(order_data['items']),
        order_data['total_amount'],
        'Preparing'
    ))
    
    conn.commit()
    conn.close()
    print(f"✅ Order {order_data['order_id']} saved to database!")
    return True

def get_all_orders():
    """Get all orders"""
    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()
    
    result = []
    for order in orders:
        order_dict = dict(order)
        order_dict['items'] = json.loads(order_dict['items'])
        result.append(order_dict)
    return result

def update_order_status(order_id, status):
    """Update order status"""
    conn = get_db_connection()
    conn.execute('UPDATE orders SET order_status = ? WHERE order_id = ?', (status, order_id))
    conn.commit()
    conn.close()
    return True

def get_dashboard_stats():
    """Get dashboard statistics"""
    conn = get_db_connection()
    
    total_orders = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
    revenue = conn.execute('SELECT SUM(total_amount) FROM orders').fetchone()[0] or 0
    pending = conn.execute('SELECT COUNT(*) FROM orders WHERE order_status = "Preparing"').fetchone()[0]
    
    conn.close()
    
    return {
        'total_orders': total_orders,
        'revenue': round(revenue, 2),
        'avg_order': round(revenue / total_orders, 2) if total_orders > 0 else 0,
        'pending': pending
    }

# ============================================================================
# CHATBOT AI LOGIC
# ============================================================================

class RestaurantChatbot:
    """AI Chatbot for restaurant ordering"""
    
    def __init__(self):
        self.sessions = {}
    
    def get_session(self, session_id):
        """Get or create session"""
        if session_id not in self.sessions:
            self.sessions[session_id] = {'cart': [], 'conversation': []}
        return self.sessions[session_id]
    
    def process_message(self, message, session_id):
        """Process user message and return response"""
        session = self.get_session(session_id)
        msg = message.lower().strip()
        
        # Greeting
        if any(word in msg for word in ['hi', 'hello', 'hey', 'good morning', 'good evening']):
            return {
                'response': "👋 Welcome to DeliciousBites!\n\nI'm your AI ordering assistant. How can I help?\n\n🍕 Browse Menu\n🔥 Hot Picks\n🛒 View Cart\n📦 Place Order\n\nWhat would you like to order today?",
                'quick_replies': ['Show Menu', 'Hot Picks', 'View Cart']
            }
        
        # Menu
        if any(word in msg for word in ['menu', 'show', 'list', 'items']):
            menu_items = get_all_menu_items()
            categories = {}
            for item in menu_items:
                if item['category'] not in categories:
                    categories[item['category']] = []
                categories[item['category']].append(item)
            
            response = "📋 **Our Complete Menu:**\n\n"
            for category, items in categories.items():
                response += f"**{category}:**\n"
                for item in items:
                    hot = "🔥 " if category == 'Hot Picks' else ""
                    response += f"{hot}{item['id']}. {item['name']} - ${item['price']}\n"
                response += "\n"
            response += "Type item number to add to cart (e.g., 'add 1')"
            
            return {
                'response': response,
                'quick_replies': ['Add 1', 'Add 2', 'View Cart']
            }
        
        # Hot Picks
        if any(word in msg for word in ['hot', 'popular', 'special', 'recommend']):
            hot_items = get_menu_by_category('Hot Picks')
            response = "🔥 **Today's Hot Picks:**\n\n"
            for item in hot_items:
                response += f"**{item['id']}. {item['name']}** - ${item['price']}\n"
                response += f"⭐ {item['rating']} | {item['description']}\n\n"
            response += "Type 'add [number]' to add to cart!"
            
            return {
                'response': response,
                'quick_replies': ['Add 1', 'Add 2', 'Add 3', 'View Cart']
            }
        
        # Add to cart
        if 'add' in msg or 'order' in msg or 'want' in msg or 'buy' in msg:
            import re
            match = re.search(r'\b(\d+)\b', msg)
            if match:
                item_id = int(match.group(1))
                item = get_item_by_id(item_id)
                if item:
                    session['cart'].append(item)
                    return {
                        'response': f"✅ **Added to Cart!**\n\n{item['image']} {item['name']} - ${item['price']}\n\n🛒 Cart: {len(session['cart'])} items\n\nContinue shopping or proceed to checkout?",
                        'quick_replies': ['View Cart', 'Checkout', 'Add More']
                    }
            return {
                'response': "Please provide item number (e.g., 'add 1')",
                'quick_replies': ['Show Menu', 'Hot Picks']
            }
        
        # View cart
        if 'cart' in msg or 'basket' in msg:
            if not session['cart']:
                return {
                    'response': "🛒 Your cart is empty!\n\nBrowse our menu to add items.",
                    'quick_replies': ['Show Menu', 'Hot Picks']
                }
            
            response = "🛒 **Your Cart:**\n\n"
            total = 0
            for idx, item in enumerate(session['cart'], 1):
                response += f"{idx}. {item['name']} - ${item['price']}\n"
                total += item['price']
            response += f"\n**Total: ${total:.2f}**\n\nReady to checkout?"
            
            return {
                'response': response,
                'quick_replies': ['Checkout', 'Clear Cart', 'Add More']
            }
        
        # Clear cart
        if 'clear' in msg and 'cart' in msg:
            session['cart'] = []
            return {
                'response': "🗑️ Cart cleared!",
                'quick_replies': ['Show Menu', 'Hot Picks']
            }
        
        # Checkout
        if 'checkout' in msg or 'place order' in msg or 'confirm' in msg:
            if not session['cart']:
                return {
                    'response': "❌ Cart is empty! Add items first.",
                    'quick_replies': ['Show Menu', 'Hot Picks']
                }
            return {
                'response': "📝 **Ready to place your order!**\n\nPlease provide your details in the form that will appear.",
                'quick_replies': [],
                'action': 'show_checkout_form'
            }
        
        # Help
        if 'help' in msg:
            return {
                'response': "🤖 **I can help you with:**\n\n🍕 Browse Menu\n🔥 Hot Picks\n🛒 Cart Management\n💳 Checkout\n\nWhat would you like to do?",
                'quick_replies': ['Show Menu', 'Hot Picks', 'View Cart']
            }
        
        # Default
        return {
            'response': "🤔 Try:\n• 'show menu'\n• 'hot picks'\n• 'add 1'\n• 'checkout'\n• 'help'",
            'quick_replies': ['Show Menu', 'Hot Picks', 'Help']
        }

# Initialize chatbot
chatbot = RestaurantChatbot()

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve main page"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Process chat message"""
    try:
        data = request.json
        message = data.get('message', '')
        session_id = data.get('session_id', 'default')
        
        result = chatbot.process_message(message, session_id)
        
        return jsonify({
            'success': True,
            'response': result['response'],
            'quick_replies': result.get('quick_replies', []),
            'action': result.get('action', None)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-cart', methods=['POST'])
def get_cart():
    """Get cart contents"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        session = chatbot.get_session(session_id)
        
        total = sum(item['price'] for item in session['cart'])
        
        return jsonify({
            'success': True,
            'cart': session['cart'],
            'total': round(total, 2)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/place-order', methods=['POST'])
def place_order():
    """Place order"""
    try:
        data = request.json
        session_id = data.get('session_id', 'default')
        customer_name = data.get('customer_name')
        customer_address = data.get('customer_address')
        customer_phone = data.get('customer_phone')
        
        session = chatbot.get_session(session_id)
        
        if not session['cart']:
            return jsonify({'success': False, 'error': 'Cart is empty'}), 400
        
        order_id = f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}"
        total = sum(item['price'] for item in session['cart'])
        
        order_data = {
            'order_id': order_id,
            'customer_name': customer_name,
            'customer_address': customer_address,
            'customer_phone': customer_phone,
            'items': session['cart'],
            'total_amount': total
        }
        
        save_order(order_data)
        session['cart'] = []  # Clear cart
        
        return jsonify({
            'success': True,
            'order_id': order_id,
            'total': round(total, 2),
            'message': f"Order placed successfully! Order ID: {order_id}"
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Get all orders"""
    try:
        orders = get_all_orders()
        return jsonify({'success': True, 'orders': orders})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get dashboard statistics"""
    try:
        stats = get_dashboard_stats()
        return jsonify({'success': True, 'stats': stats})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cancel-order', methods=['POST'])
def cancel_order():
    """Cancel order"""
    try:
        data = request.json
        order_id = data.get('order_id')
        
        update_order_status(order_id, 'Cancelled')
        
        return jsonify({
            'success': True,
            'message': f'Order {order_id} cancelled successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Create necessary directories
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    print("\n" + "="*70)
    print("🍕 DELICIOUSBITES RESTAURANT CHATBOT")
    print("="*70)
    print("\n📍 Server starting at: http://localhost:5000")
    print("📊 Database: database.db")
    print("🤖 AI Chatbot: Ready")
    print("\n💡 Press Ctrl+C to stop\n")
    print("="*70 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True)