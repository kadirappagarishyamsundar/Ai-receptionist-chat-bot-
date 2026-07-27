from flask import Blueprint, render_template, jsonify, request
from database import db

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
def dashboard():
    """Admin dashboard"""
    return render_template('admin_dashboard.html')

@admin_bp.route('/api/appointments')
def get_appointments():
    """Get all appointments"""
    try:
        query = """
        SELECT id, customer_name, email, service_type, appointment_date, 
               TIME_FORMAT(appointment_time, '%H:%i:%s') AS appointment_time, 
               status, created_at 
        FROM appointments 
        ORDER BY created_at DESC
        """
        appointments = db.execute_query(query)
        return jsonify({'appointments': appointments}), 200
    except Exception as e:
        print(f"❌ Error fetching appointments: {e}")
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/appointments/<int:id>', methods=['PUT'])
def update_appointment(id):
    """Update appointment status"""
    try:
        data = request.json
        status = data.get('status')
        
        query = "UPDATE appointments SET status = %s WHERE id = %s"
        db.update_data(query, (status, id))
        
        return jsonify({'message': 'Appointment updated'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/appointments/<int:id>', methods=['DELETE'])
def delete_appointment(id):
    """Delete appointment"""
    try:
        query = "DELETE FROM appointments WHERE id = %s"
        db.update_data(query, (id,))
        return jsonify({'message': 'Appointment deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_bp.route('/api/stats')
def get_stats():
    """Get dashboard statistics"""
    try:
        # Total appointments
        total = db.execute_query("SELECT COUNT(*) as count FROM appointments")
        
        # Completed appointments
        completed = db.execute_query(
            "SELECT COUNT(*) as count FROM appointments WHERE status = 'completed'"
        )
        
        # Pending appointments
        pending = db.execute_query(
            "SELECT COUNT(*) as count FROM appointments WHERE status = 'pending'"
        )
        
        # Most booked service
        services = db.execute_query("""
            SELECT service_type, COUNT(*) as count 
            FROM appointments 
            GROUP BY service_type 
            ORDER BY count DESC 
            LIMIT 5
        """)
        
        return jsonify({
            'total': total[0]['count'] if total else 0,
            'completed': completed[0]['count'] if completed else 0,
            'pending': pending[0]['count'] if pending else 0,
            'top_services': services
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500