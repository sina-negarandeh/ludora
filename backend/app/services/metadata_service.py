from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database.models import Category, Theme, Subdomain, Mechanic, Designer, Publisher, GameTheme, GameSubdomain, Family, Subfamily, GameSubfamily

class MetadataService:
    def __init__(self, db: Session):
        self.db = db

    def get_categories(self, search: str = None, limit: int = None) -> List[str]:
        query = self.db.query(Category.name)
        if search:
            query = query.filter(Category.name.ilike(f"%{search}%"))
        query = query.order_by(Category.name)
        if limit:
            query = query.limit(limit)
        return [c[0] for c in query.all()]

    def get_subdomains(self, search: str = None, limit: int = None) -> List[dict]:
        query = self.db.query(
            Subdomain.id,
            Subdomain.name,
            func.count(GameSubdomain.game_id).label("game_count")
        ).join(GameSubdomain, Subdomain.id == GameSubdomain.subdomain_id)

        if search:
            query = query.filter(Subdomain.name.ilike(f"%{search}%"))

        query = query.group_by(Subdomain.id).order_by(Subdomain.name)
        if limit:
            query = query.limit(limit)

        subdomains = query.all()
        return [{"id": s.id, "name": s.name, "game_count": s.game_count} for s in subdomains]

    def get_mechanics(self, search: str = None, limit: int = None) -> List[str]:
        query = self.db.query(Mechanic.name)
        if search:
            query = query.filter(Mechanic.name.ilike(f"%{search}%"))
        query = query.order_by(Mechanic.name)
        if limit:
            query = query.limit(limit)
        return [m[0] for m in query.all()]

    def get_designers(self, search: str = None, limit: int = None) -> List[str]:
        query = self.db.query(Designer.name)
        if search:
            query = query.filter(Designer.name.ilike(f"%{search}%"))
        query = query.order_by(Designer.name)
        if limit:
            query = query.limit(limit)
        return [d[0] for d in query.all()]

    def get_publishers(self, search: str = None, limit: int = None) -> List[str]:
        query = self.db.query(Publisher.name)
        if search:
            query = query.filter(Publisher.name.ilike(f"%{search}%"))
        query = query.order_by(Publisher.name)
        if limit:
            query = query.limit(limit)
        return [p[0] for p in query.all()]

    def get_themes(self, search: str = None, limit: int = None) -> List[dict]:
        query = self.db.query(
            Theme.id, 
            Theme.name, 
            func.count(GameTheme.game_id).label("game_count")
        ).join(GameTheme, Theme.id == GameTheme.theme_id)
        
        if search:
            query = query.filter(Theme.name.ilike(f"%{search}%"))
            
        query = query.group_by(Theme.id).order_by(Theme.name)
        if limit:
            query = query.limit(limit)
            
        themes = query.all()
        return [{"id": t.id, "name": t.name, "game_count": t.game_count} for t in themes]

    def get_families(self, search: str = None) -> List[dict]:
        query = self.db.query(
            Family.name.label("group_name"),
            Subfamily.id,
            Subfamily.value,
            Subfamily.name,
            func.count(GameSubfamily.game_id).label("game_count"),
        ).select_from(Subfamily).join(
            Family, Subfamily.family_id == Family.id
        ).join(
            GameSubfamily, Subfamily.id == GameSubfamily.subfamily_id
        )

        if search:
            query = query.filter(Subfamily.value.ilike(f"%{search}%"))

        query = query.group_by(Family.name, Subfamily.id).order_by(Family.name, Subfamily.value)
        rows = query.all()

        grouped: dict[str, list] = {}
        for r in rows:
            grouped.setdefault(r.group_name, []).append(
                {"id": r.id, "value": r.value, "name": r.name, "game_count": r.game_count}
            )
        return [{"group": g, "values": vals} for g, vals in grouped.items()]

    def get_artists(self, search: str = None, limit: int = None) -> List[str]:
        from app.database.models import Artist
        query = self.db.query(Artist.name)
        if search:
            query = query.filter(Artist.name.ilike(f"%{search}%"))
        query = query.order_by(Artist.name)
        if limit:
            query = query.limit(limit)
        return [a[0] for a in query.all()]
