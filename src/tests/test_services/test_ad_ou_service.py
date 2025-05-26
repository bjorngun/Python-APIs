from python_apis.services.ad_group_service import ADGroupService


def main():
    ad_ou = ADGroupService()
    ad_ou.create_table()
    ad_ou.update_group_db()

if __name__ == '__main__':
    main()
