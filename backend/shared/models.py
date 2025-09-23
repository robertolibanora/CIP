"""
Modelli Python per le entità del database CIP Immobiliare
Implementa tutti i modelli richiesti per KYC, Portafoglio, Ricariche, Prelievi e Rendimenti
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from dataclasses import dataclass
from enum import Enum

# ============================================================================
# ENUMERAZIONI
# ============================================================================

class KYCStatus(str, Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"

class UserRole(str, Enum):
    ADMIN = "admin"
    INVESTOR = "investor"

class DocumentVisibility(str, Enum):
    PRIVATE = "private"
    ADMIN = "admin"
    PUBLIC = "public"

class TransactionStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TransactionType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    INVESTMENT = "investment"
    RA = "roi"  # Rendimento Annuo
    REFERRAL = "referral"

class InvestmentStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ProjectStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SOLD = "sold"

# ============================================================================
# MODELLI BASE
# ============================================================================

@dataclass
class User:
    """Modello utente con gestione KYC"""
    id: Optional[int]
    email: str
    password_hash: str
    nome: str
    nome: str
    cognome: str
    telegram: str
    telefono: str
    address: Optional[str]
    role: UserRole
    kyc_status: KYCStatus
    currency_code: str
    referral_code: Optional[str]
    referral_link: Optional[str]
    referred_by: Optional[int]
    is_vip: bool
    created_at: datetime
    
    def is_kyc_verified(self) -> bool:
        """Verifica se l'utente ha KYC approvato"""
        return self.kyc_status == KYCStatus.VERIFIED
    
    def can_invest(self) -> bool:
        """Verifica se l'utente può investire"""
        return self.is_kyc_verified() and self.role == UserRole.INVESTOR
    
    def is_vip_user(self) -> bool:
        """Verifica se l'utente è VIP"""
        return self.is_vip

@dataclass
class Document:
    """Modello documento per sistema KYC"""
    id: Optional[int]
    user_id: int
    category_id: int
    title: Optional[str]
    file_path: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    visibility: DocumentVisibility
    verified_by_admin: bool
    uploaded_at: datetime

@dataclass
class DocumentCategory:
    """Modello categoria documento"""
    id: Optional[int]
    slug: str
    name: str
    is_kyc: bool

# ============================================================================
# MODELLI PORTFOLIO - 4 SEZIONI DISTINTE
# ============================================================================

@dataclass
class UserPortfolio:
    """Modello portafoglio utente con 4 sezioni distinte"""
    id: Optional[int]
    user_id: int
    
    # 1. Capitale Libero - Soldi non investiti, sempre prelevabili
    free_capital: Decimal
    
    # 2. Capitale Investito - bloccato fino alla vendita dell'immobile
    invested_capital: Decimal
    
    # 3. Bonus - 3% referral, sempre disponibili per prelievo/investimento (5% se sei un utente VIP)
    referral_bonus: Decimal
    
    # 4. Profitti - Rendimenti accumulati, prelevabili o reinvestibili
    profits: Decimal
    
    created_at: datetime
    updated_at: datetime
    
    def total_balance(self) -> Decimal:
        """Calcola il saldo totale disponibile"""
        return self.free_capital + self.referral_bonus + self.profits
    
    def available_for_investment(self) -> Decimal:
        """Capitale disponibile per investimenti"""
        return self.free_capital + self.referral_bonus
    
    def locked_capital(self) -> Decimal:
        """Capitale bloccato negli investimenti"""
        return self.invested_capital

@dataclass
class PortfolioTransaction:
    """Modello transazione portafoglio"""
    id: Optional[int]
    user_id: int
    type: TransactionType
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    description: str
    reference_id: Optional[int]
    reference_type: Optional[str]
    status: TransactionStatus
    created_at: datetime

# ============================================================================
# MODELLI SISTEMA RICARICHE
# ============================================================================

@dataclass
class DepositRequest:
    """Modello richiesta ricarica"""
    id: Optional[int]
    user_id: int
    amount: Decimal
    iban: str
    unique_key: str  # 6 caratteri alfanumerici
    payment_reference: str  # Chiave randomica per causale bonifico
    status: TransactionStatus
    admin_notes: Optional[str]
    created_at: datetime
    approved_at: Optional[datetime]
    approved_by: Optional[int]
    
    def is_minimum_amount(self) -> bool:
        """Verifica se l'importo rispetta il minimo di 500€"""
        return self.amount >= Decimal('500.00')

@dataclass
class IBANConfiguration:
    """Modello configurazione IBAN per ricariche"""
    id: Optional[int]
    iban: str
    bank_name: str
    account_holder: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

# ============================================================================
# MODELLI SISTEMA PRELIEVI
# ============================================================================

@dataclass
class WithdrawalRequest:
    """Modello richiesta prelievo"""
    id: Optional[int]
    user_id: int
    amount: Decimal
    method: str  # usdt, bank
    source_section: str  # free_capital, referral_bonus, profits
    wallet_address: Optional[str]  # Per prelievi USDT (BEP20)
    bank_details: Optional[dict]  # JSON con IBAN, intestatario, banca
    unique_key: str  # 6 caratteri alfanumerici
    status: TransactionStatus
    admin_notes: Optional[str]
    created_at: datetime
    approved_at: Optional[datetime]
    approved_by: Optional[int]
    
    def is_minimum_amount(self) -> bool:
        """Verifica se l'importo rispetta il minimo di 50 dollari"""
        return self.amount >= Decimal('50.00')
    
    def is_from_valid_section(self) -> bool:
        """Verifica se la sezione di prelievo è valida"""
        valid_sections = ['free_capital', 'referral_bonus', 'profits']
        return self.source_section in valid_sections
    
    def is_valid_method(self) -> bool:
        """Verifica se il metodo di prelievo è valido"""
        return self.method in ['usdt', 'bank']
    
    def has_required_fields(self) -> bool:
        """Verifica se ha i campi richiesti in base al metodo"""
        if self.method == 'usdt':
            return bool(self.wallet_address)
        elif self.method == 'bank':
            return bool(self.bank_details)
        return False

# ============================================================================
# MODELLI SISTEMA RENDIMENTI E VENDITE
# ============================================================================

@dataclass
class Investment:
    """Modello investimento con gestione rendimenti"""
    id: Optional[int]
    user_id: int
    project_id: int
    amount: Decimal
    percentage: Decimal
    status: InvestmentStatus
    roi_earned: Decimal
    investment_date: datetime
    completion_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

@dataclass
class ProjectSale:
    """Modello vendita progetto immobiliare"""
    id: Optional[int]
    project_id: int
    sale_price: Decimal
    sale_date: datetime
    admin_id: int
    created_at: datetime
    
    def calculate_profits(self, total_invested: Decimal) -> Decimal:
        """Calcola i profitti totali dalla vendita"""
        if total_invested > 0:
            profit = self.sale_price - total_invested
            # Se la vendita è in perdita, restituisci 0 invece di un valore negativo
            return max(profit, Decimal('0.00'))
        return Decimal('0.00')

@dataclass
class ProfitDistribution:
    """Modello distribuzione profitti e referral"""
    id: Optional[int]
    project_sale_id: int
    user_id: int
    investment_id: int
    original_investment: Decimal
    profit_share: Decimal
    referral_bonus: Decimal  # 3% del profitto per chi ha invitato (5% se sei un utente VIP)
    total_payout: Decimal
    status: TransactionStatus
    created_at: datetime
    paid_at: Optional[datetime]

# ============================================================================
# MODELLI SISTEMA REFERRAL
# ============================================================================

@dataclass
class Referral:
    """Modello sistema referral"""
    id: Optional[int]
    referrer_id: int
    referred_user_id: int
    referral_code: str
    status: str
    first_investment_date: Optional[datetime]
    total_invested: Decimal
    commission_earned: Decimal
    created_at: datetime
    updated_at: datetime

@dataclass
class ReferralCommission:
    """Modello commissione referral"""
    id: Optional[int]
    referral_id: int
    referrer_id: int
    referred_user_id: int
    investment_id: int
    project_id: int
    investment_amount: Decimal
    commission_amount: Decimal
    status: TransactionStatus
    payout_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime

# ============================================================================
# MODELLI PROGETTI
# ============================================================================

@dataclass
class Project:
    """Modello progetto immobiliare"""
    id: Optional[int]
    name: str
    description: str
    location: str
    type: str
    total_amount: Decimal
    funded_amount: Decimal
    min_investment: Decimal
    roi: Decimal
    status: ProjectStatus
    start_date: datetime
    image_url: Optional[str]
    documents: Optional[dict]
    gallery: Optional[dict]
    created_at: datetime
    updated_at: datetime
    # Nuovi campi per gestione vendite
    sale_price: Optional[Decimal] = None
    sale_date: Optional[datetime] = None
    profit_percentage: Optional[Decimal] = None
    sold_by_admin_id: Optional[int] = None
    
    def funding_progress(self) -> Decimal:
        """Calcola la percentuale di finanziamento"""
        if self.total_amount > 0:
            return (self.funded_amount / self.total_amount) * Decimal('100.00')
        return Decimal('0.00')
    
    def is_funded(self) -> bool:
        """Verifica se il progetto è completamente finanziato"""
        return self.funded_amount >= self.total_amount
    
    def can_invest(self) -> bool:
        """Verifica se è possibile investire nel progetto"""
        from datetime import date
        # Progetto deve essere attivo
        return self.status == ProjectStatus.ACTIVE
    
    def is_completed(self) -> bool:
        """Verifica se il progetto è completato (non si può più investire)"""
        return self.status == ProjectStatus.COMPLETED
    
    def is_sold(self) -> bool:
        """Verifica se il progetto è stato venduto"""
        return self.status == ProjectStatus.SOLD
    
    def get_profit_info(self) -> dict:
        """Restituisce informazioni sui profitti se il progetto è venduto"""
        if not self.is_sold() or not self.sale_price:
            return {}
        
        profit_amount = self.sale_price - self.total_amount
        return {
            'sale_price': self.sale_price,
            'profit_amount': profit_amount,
            'profit_percentage': self.profit_percentage or Decimal('0.00'),
            'sale_date': self.sale_date
        }

